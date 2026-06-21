// SPDX-License-Identifier: MIT
pragma solidity ^0.8.27;

import "../libraries/LibLifecycleStorage.sol";
import "../libraries/LibLifecycleCore.sol";
import "../libraries/LibAccessControl.sol";
import "../libraries/LifecycleEvents.sol";

contract LifecycleCore {
    using LibLifecycleStorage for LibLifecycleStorage.Layout;

    // Aliases for shorter call sites.
    type S is uint8;
    function _s(LibLifecycleStorage.Status v) private pure returns (S) { return S.wrap(uint8(v)); }

    function createModelCard(address creator, string memory metadataURI, bytes32 contentHash)
        external
        returns (uint256)
    {
        LibAccessControl.checkRole(LibAccessControl.DEVELOPER_ROLE);
        require(creator != address(0), "Actor required");
        require(bytes(metadataURI).length > 0, "Metadata URI required");
        require(contentHash != bytes32(0), "Content hash required");

        LibLifecycleStorage.Layout storage l = LibLifecycleStorage.layout();
        l.tokenIdCounter += 1;
        uint256 newTokenId = l.tokenIdCounter;

        // Soulbound mint via shared NFT storage (no-OZ).
        _safeMint(creator, newTokenId);

        l.modelCards[newTokenId] = LibLifecycleStorage.ModelCard({
            tokenId: newTokenId,
            creator: creator,
            metadataURI: metadataURI,
            contentHash: contentHash,
            status: LibLifecycleStorage.Status.Created,
            createdAt: block.timestamp,
            lastUpdated: block.timestamp,
            revisionNotes: "",
            lastModifiedBy: creator,
            isActive: true,
            version: 1,
            revisionCount: 0
        });
        l.statusHistory[newTokenId].push(LibLifecycleStorage.Status.Created);

        LibLifecycleCore.recordAction(
            newTokenId,
            creator,
            LibLifecycleStorage.Status.Created,
            LibLifecycleStorage.Status.Created,
            LibLifecycleStorage.TransitionType.Create,
            contentHash
        );

        emit LifecycleEvents.ModelCardCreated(newTokenId, creator, metadataURI, contentHash, block.timestamp);
        return newTokenId;
    }

    function submitForEvaluation(uint256 tokenId, address actor) external {
        LibAccessControl.checkRole(LibAccessControl.DEVELOPER_ROLE);
        require(actor != address(0), "Actor required");
        LibLifecycleStorage.Layout storage l = LibLifecycleStorage.layout();
        LibLifecycleStorage.ModelCard storage card = l.modelCards[tokenId];
        require(card.isActive, "Model card not active");
        require(
            card.status == LibLifecycleStorage.Status.Created ||
            card.status == LibLifecycleStorage.Status.Revised,
            "Invalid status for submission"
        );

        LibLifecycleStorage.Status fromState = card.status;
        LibLifecycleCore.updateStatus(tokenId, LibLifecycleStorage.Status.InEvaluation, actor);
        LibLifecycleCore.recordAction(
            tokenId, actor, fromState, LibLifecycleStorage.Status.InEvaluation,
            LibLifecycleStorage.TransitionType.Submit, card.contentHash
        );
        emit LifecycleEvents.ModelCardSubmitted(tokenId, actor, block.timestamp);
    }

    function validateModelCard(uint256 tokenId, address actor) external {
        LibAccessControl.checkRole(LibAccessControl.AUTHENTICATOR_ROLE);
        require(actor != address(0), "Actor required");
        LibLifecycleStorage.Layout storage l = LibLifecycleStorage.layout();
        LibLifecycleStorage.ModelCard storage card = l.modelCards[tokenId];
        require(card.isActive, "Model card not active");
        require(card.status == LibLifecycleStorage.Status.InEvaluation, "Not in evaluation");

        LibLifecycleCore.updateStatus(tokenId, LibLifecycleStorage.Status.Validated, actor);
        LibLifecycleCore.recordAction(
            tokenId, actor,
            LibLifecycleStorage.Status.InEvaluation, LibLifecycleStorage.Status.Validated,
            LibLifecycleStorage.TransitionType.Validate, card.contentHash
        );
        emit LifecycleEvents.ModelCardValidated(tokenId, actor, block.timestamp);
    }

    function rejectModelCard(uint256 tokenId, string memory reason, address actor) external {
        LibAccessControl.checkRole(LibAccessControl.AUTHENTICATOR_ROLE);
        require(actor != address(0), "Actor required");
        LibLifecycleStorage.Layout storage l = LibLifecycleStorage.layout();
        LibLifecycleStorage.ModelCard storage card = l.modelCards[tokenId];
        require(card.isActive, "Model card not active");
        require(card.status == LibLifecycleStorage.Status.InEvaluation, "Not in evaluation");

        LibLifecycleCore.updateStatus(tokenId, LibLifecycleStorage.Status.Rejected, actor);
        card.isActive = false;
        card.revisionNotes = reason;
        LibLifecycleCore.recordAction(
            tokenId, actor,
            LibLifecycleStorage.Status.InEvaluation, LibLifecycleStorage.Status.Rejected,
            LibLifecycleStorage.TransitionType.Reject, card.contentHash
        );
        emit LifecycleEvents.ModelCardRejected(tokenId, actor, reason, block.timestamp);
    }

    function requestRevision(uint256 tokenId, string memory feedback, address actor) external {
        LibAccessControl.checkRole(LibAccessControl.AUTHENTICATOR_ROLE);
        require(actor != address(0), "Actor required");
        LibLifecycleStorage.Layout storage l = LibLifecycleStorage.layout();
        LibLifecycleStorage.ModelCard storage card = l.modelCards[tokenId];
        require(card.isActive, "Model card not active");
        require(card.status == LibLifecycleStorage.Status.InEvaluation, "Not in evaluation");

        LibLifecycleCore.updateStatus(tokenId, LibLifecycleStorage.Status.RevisionRequested, actor);
        card.revisionNotes = feedback;
        LibLifecycleCore.recordAction(
            tokenId, actor,
            LibLifecycleStorage.Status.InEvaluation, LibLifecycleStorage.Status.RevisionRequested,
            LibLifecycleStorage.TransitionType.RequestRevision, card.contentHash
        );
        emit LifecycleEvents.RevisionRequested(tokenId, actor, feedback, block.timestamp);
    }

    uint256 internal constant MAX_REVISIONS = 10;

    function reviseModelCard(
        uint256 tokenId,
        string memory newMetadataURI,
        bytes32 newContentHash,
        string memory revisionNotes,
        address actor
    ) external {
        LibAccessControl.checkRole(LibAccessControl.DEVELOPER_ROLE);
        require(actor != address(0), "Actor required");
        LibLifecycleStorage.Layout storage l = LibLifecycleStorage.layout();
        LibLifecycleStorage.ModelCard storage card = l.modelCards[tokenId];
        require(card.isActive, "Model card not active");
        require(card.status == LibLifecycleStorage.Status.RevisionRequested, "Revision not requested");
        require(newContentHash != bytes32(0), "Content hash required");
        require(card.revisionCount < MAX_REVISIONS, "Maximum revisions reached");

        l.revisionHistory[tokenId].push(LibLifecycleStorage.RevisionRecord({
            revisionNumber: card.revisionCount + 1,
            previousMetadataURI: card.metadataURI,
            previousContentHash: card.contentHash,
            newMetadataURI: newMetadataURI,
            newContentHash: newContentHash,
            revisionNotes: revisionNotes,
            revisedBy: actor,
            timestamp: block.timestamp
        }));

        emit LifecycleEvents.RevisionHistoryRecorded(
            tokenId,
            card.revisionCount + 1,
            card.contentHash,
            newContentHash,
            actor,
            block.timestamp
        );

        card.metadataURI = newMetadataURI;
        card.contentHash = newContentHash;
        card.revisionNotes = revisionNotes;
        card.version++;
        card.revisionCount++;

        LibLifecycleCore.updateStatus(tokenId, LibLifecycleStorage.Status.Revised, actor);
        LibLifecycleCore.recordAction(
            tokenId, actor,
            LibLifecycleStorage.Status.RevisionRequested, LibLifecycleStorage.Status.Revised,
            LibLifecycleStorage.TransitionType.Revise, newContentHash
        );
        emit LifecycleEvents.ModelCardRevised(
            tokenId, actor, newMetadataURI, newContentHash, revisionNotes, block.timestamp
        );
    }

    function publishModelCard(uint256 tokenId, address actor) external {
        LibAccessControl.checkRole(LibAccessControl.PUBLISHER_ROLE);
        require(actor != address(0), "Actor required");
        LibLifecycleStorage.Layout storage l = LibLifecycleStorage.layout();
        LibLifecycleStorage.ModelCard storage card = l.modelCards[tokenId];
        require(card.isActive, "Model card not active");
        require(card.status == LibLifecycleStorage.Status.Validated, "Not validated");

        LibLifecycleCore.updateStatus(tokenId, LibLifecycleStorage.Status.Published, actor);
        LibLifecycleCore.recordAction(
            tokenId, actor,
            LibLifecycleStorage.Status.Validated, LibLifecycleStorage.Status.Published,
            LibLifecycleStorage.TransitionType.Publish, card.contentHash
        );
        LibLifecycleCore.mintProvenanceSBT(tokenId, card);
        emit LifecycleEvents.ModelCardPublished(tokenId, actor, block.timestamp);
    }

    function deprecateModelCard(uint256 tokenId, string memory reason, address actor) external {
        LibAccessControl.checkRole(LibAccessControl.PUBLISHER_ROLE);
        require(actor != address(0), "Actor required");
        LibLifecycleStorage.Layout storage l = LibLifecycleStorage.layout();
        LibLifecycleStorage.ModelCard storage card = l.modelCards[tokenId];
        require(card.isActive, "Model card not active");
        require(card.status == LibLifecycleStorage.Status.Published, "Not published");

        LibLifecycleCore.updateStatus(tokenId, LibLifecycleStorage.Status.Deprecated, actor);
        card.isActive = false;
        card.revisionNotes = reason;
        LibLifecycleCore.recordAction(
            tokenId, actor,
            LibLifecycleStorage.Status.Published, LibLifecycleStorage.Status.Deprecated,
            LibLifecycleStorage.TransitionType.Deprecate, card.contentHash
        );
        emit LifecycleEvents.ModelCardDeprecated(tokenId, actor, reason, block.timestamp);
    }

    function _safeMint(address to, uint256 tokenId) private {
        require(to != address(0), "ERC721: mint to the zero address");
        LibLifecycleStorage.Layout storage l = LibLifecycleStorage.layout();
        require(l.erc721Owners[tokenId] == address(0), "ERC721: token already minted");
        l.erc721Balances[to] += 1;
        l.erc721Owners[tokenId] = to;
        emit LifecycleEvents.Transfer(address(0), to, tokenId);
        emit LifecycleEvents.Locked(tokenId);
    }
}
