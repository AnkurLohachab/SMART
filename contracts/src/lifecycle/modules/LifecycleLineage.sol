// SPDX-License-Identifier: MIT
pragma solidity ^0.8.27;

import "../libraries/LibLifecycleStorage.sol";
import "../libraries/LibLifecycleCore.sol";
import "../libraries/LibAccessControl.sol";
import "../libraries/LifecycleEvents.sol";

contract LifecycleLineage {
    function createModelCardWithLineage(
        address creator,
        string calldata name,
        string calldata metadataURI,
        bytes32 contentHash,
        uint256 supersedes,
        SMARTVersionRegistry.Relation relation,
        bool withinEnvelope
    ) external returns (uint256 tokenId, bytes memory aliasOut) {
        LibAccessControl.checkRole(LibAccessControl.DEVELOPER_ROLE);
        LibLifecycleStorage.Layout storage l = LibLifecycleStorage.layout();
        require(address(l.nameRegistry) != address(0), "Name registry not configured");
        require(address(l.versionRegistry) != address(0), "Version registry not configured");
        require(creator != address(0), "Actor required");
        require(bytes(metadataURI).length > 0, "Metadata URI required");
        require(contentHash != bytes32(0), "Content hash required");
        require(bytes(name).length > 0, "Name required");

        l.tokenIdCounter += 1;
        tokenId = l.tokenIdCounter;
        _safeMint(creator, tokenId);

        l.modelCards[tokenId] = LibLifecycleStorage.ModelCard({
            tokenId: tokenId,
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
        l.statusHistory[tokenId].push(LibLifecycleStorage.Status.Created);

        LibLifecycleCore.recordAction(
            tokenId,
            creator,
            LibLifecycleStorage.Status.Created,
            LibLifecycleStorage.Status.Created,
            LibLifecycleStorage.TransitionType.Create,
            contentHash
        );

        aliasOut = l.nameRegistry.claimName(name, creator);
        bytes32 nh = keccak256(bytes(name));
        l.versionRegistry.mintVersion(
            tokenId,
            nh,
            supersedes,
            relation,
            withinEnvelope,
            creator
        );

        emit LifecycleEvents.ModelCardCreated(tokenId, creator, metadataURI, contentHash, block.timestamp);
    }

    function pinLineEnvelope(string calldata name, bytes32 envelopeHash, address controller) external {
        LibAccessControl.checkRole(LibAccessControl.DEVELOPER_ROLE);
        LibLifecycleStorage.Layout storage l = LibLifecycleStorage.layout();
        require(address(l.versionRegistry) != address(0), "Version registry not configured");
        bytes32 nh = keccak256(bytes(name));
        l.versionRegistry.pinEnvelope(nh, envelopeHash, controller);
    }

    function updateLineEnvelope(string calldata name, bytes32 newHash, address controller) external {
        LibAccessControl.checkRole(LibAccessControl.DEVELOPER_ROLE);
        LibLifecycleStorage.Layout storage l = LibLifecycleStorage.layout();
        require(address(l.versionRegistry) != address(0), "Version registry not configured");
        bytes32 nh = keccak256(bytes(name));
        l.versionRegistry.updateEnvelope(nh, newHash, controller);
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
