// SPDX-License-Identifier: MIT
pragma solidity ^0.8.27;

import "./LibLifecycleStorage.sol";
import "./LifecycleEvents.sol";
import "../../core/SMARTIdentityRegistry.sol";

library LibLifecycleCore {
    using LibLifecycleStorage for LibLifecycleStorage.Layout;

    function updateStatus(
        uint256 tokenId,
        LibLifecycleStorage.Status newStatus,
        address changedBy
    ) internal {
        LibLifecycleStorage.Layout storage l = LibLifecycleStorage.layout();
        LibLifecycleStorage.ModelCard storage card = l.modelCards[tokenId];
        LibLifecycleStorage.Status oldStatus = card.status;

        card.status = newStatus;
        card.lastUpdated = block.timestamp;
        card.lastModifiedBy = changedBy;
        l.statusHistory[tokenId].push(newStatus);

        emit LifecycleEvents.StatusChanged(tokenId, oldStatus, newStatus, changedBy, block.timestamp);
    }

    function claimTypeForTransition(LibLifecycleStorage.TransitionType t) internal pure returns (uint256) {
        if (t == LibLifecycleStorage.TransitionType.Create
            || t == LibLifecycleStorage.TransitionType.Submit
            || t == LibLifecycleStorage.TransitionType.Revise) {
            return 1; // CLAIM_TYPE_ISSUER (developer attestation)
        }
        if (t == LibLifecycleStorage.TransitionType.Validate
            || t == LibLifecycleStorage.TransitionType.Reject
            || t == LibLifecycleStorage.TransitionType.RequestRevision) {
            return 2; // CLAIM_TYPE_AUTHENTICATOR
        }
        if (t == LibLifecycleStorage.TransitionType.Publish
            || t == LibLifecycleStorage.TransitionType.Deprecate
            || t == LibLifecycleStorage.TransitionType.AdminPublish
            || t == LibLifecycleStorage.TransitionType.AdminDeprecate) {
            return 3; // CLAIM_TYPE_PUBLISHER
        }
        return 0;
    }

    function recordAction(
        uint256 tokenId,
        address actor,
        LibLifecycleStorage.Status fromState,
        LibLifecycleStorage.Status toState,
        LibLifecycleStorage.TransitionType transitionType,
        bytes32 contentHash
    ) internal returns (uint256 actionId) {
        LibLifecycleStorage.Layout storage l = LibLifecycleStorage.layout();
        uint256 requiredClaimType = claimTypeForTransition(transitionType);

        SMARTIdentityRegistry.IdentitySnapshot memory snap;
        if (address(l.identityRegistry) == address(0)) {
            snap = SMARTIdentityRegistry.IdentitySnapshot({
                claimRef: bytes32(0),
                issuerRef: bytes32(0),
                subjectRef: bytes32(uint256(uint160(actor))),
                contextRef: bytes32(requiredClaimType),
                validFrom: 0,
                validUntil: 0,
                registryVersion: 0
            });
        } else {
            snap = l.identityRegistry.snapshotOf(actor, requiredClaimType);
        }

        if (l.requireIdentityForTransition[uint8(transitionType)]) {
            require(snap.claimRef != bytes32(0), "SMARTLifecycle: identity required");
        }

        LibLifecycleStorage.IdentityStatus initialStatus;
        if (snap.claimRef != bytes32(0)) {
            initialStatus = LibLifecycleStorage.IdentityStatus.Bound;
        } else if (address(l.identityRegistry) == address(0)) {
            initialStatus = LibLifecycleStorage.IdentityStatus.UnboundOptimistic;
        } else {
            initialStatus = LibLifecycleStorage.IdentityStatus.UnboundMissing;
        }

        actionId = ++l.nextActionId;
        l.actionById[actionId] = LibLifecycleStorage.ActionRecord({
            actionId: actionId,
            tokenId: tokenId,
            actor: actor,
            fromState: uint8(fromState),
            toState: uint8(toState),
            transitionType: uint8(transitionType),
            contentHash: contentHash,
            claimRef: snap.claimRef,
            issuerRef: snap.issuerRef,
            contextRef: snap.contextRef,
            timestamp: uint64(block.timestamp),
            blockNumber: uint64(block.number),
            registryVersion: snap.registryVersion,
            identityStatus: initialStatus,
            challengeReason: LibLifecycleStorage.RepudiationReason.NoClaim,
            arbiter: address(0),
            panelMember1: address(0),
            panelMember2: address(0),
            challenger: address(0)
        });
        l.actionsForToken[tokenId].push(actionId);

        emit LifecycleEvents.BoundAction(
            actionId,
            tokenId,
            actor,
            uint8(fromState),
            uint8(toState),
            uint8(transitionType),
            contentHash,
            snap.claimRef,
            snap.issuerRef,
            snap.contextRef,
            initialStatus,
            block.timestamp
        );
    }

    function mintProvenanceSBT(uint256 tokenId, LibLifecycleStorage.ModelCard storage card) internal {
        LibLifecycleStorage.Layout storage l = LibLifecycleStorage.layout();
        if (address(l.sbtContract) == address(0)) {
            return;
        }
        if (l.lifecycleToSBT[tokenId] != 0) {
            return;
        }
        uint256 sbtTokenId = l.sbtContract.mint(
            card.creator,
            card.contentHash,
            card.metadataURI,
            uintToString(card.version),
            "",
            "1.0.0", // SCHEMA_VERSION
            0,
            card.metadataURI
        );
        l.lifecycleToSBT[tokenId] = sbtTokenId;
        emit LifecycleEvents.ProvenanceSBTMinted(
            tokenId,
            sbtTokenId,
            card.contentHash,
            card.creator,
            block.timestamp
        );
    }

    function uintToString(uint256 value) internal pure returns (string memory) {
        if (value == 0) return "0";
        uint256 temp = value;
        uint256 digits;
        while (temp != 0) {
            digits++;
            temp /= 10;
        }
        bytes memory buffer = new bytes(digits);
        while (value != 0) {
            digits -= 1;
            buffer[digits] = bytes1(uint8(48 + uint256(value % 10)));
            value /= 10;
        }
        return string(buffer);
    }
}
