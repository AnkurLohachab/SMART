// SPDX-License-Identifier: MIT
pragma solidity ^0.8.27;

import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";

import "../libraries/LibLifecycleStorage.sol";
import "../libraries/LibAccessControl.sol";
import "../libraries/LifecycleEvents.sol";

contract LifecycleQuorum {
    function challengeAction(
        uint256 actionId,
        LibLifecycleStorage.RepudiationReason reason,
        address challenger
    ) external {
        LibLifecycleStorage.Layout storage l = LibLifecycleStorage.layout();
        LibLifecycleStorage.ActionRecord storage rec = l.actionById[actionId];
        require(rec.actionId != 0, "Action not found");
        require(
            rec.identityStatus == LibLifecycleStorage.IdentityStatus.Bound ||
            rec.identityStatus == LibLifecycleStorage.IdentityStatus.UnboundMissing ||
            rec.identityStatus == LibLifecycleStorage.IdentityStatus.UnboundOptimistic,
            "Action not challengeable"
        );
        require(
            l.challengeWindowSeconds == 0 ||
            block.timestamp <= rec.timestamp + l.challengeWindowSeconds,
            "Challenge window closed"
        );
        require(challenger != address(0), "Challenger required");

        rec.identityStatus = LibLifecycleStorage.IdentityStatus.Disputed;
        rec.challengeReason = reason;
        rec.challenger = challenger;

        emit LifecycleEvents.ActionChallenged(actionId, rec.tokenId, challenger, reason, block.timestamp);
    }

    function resolveDispute(
        uint256 actionId,
        LibLifecycleStorage.IdentityStatus finalStatus
    ) external {
        LibAccessControl.checkRole(LibAccessControl.IDENTITY_ARBITER_ROLE);
        require(
            finalStatus == LibLifecycleStorage.IdentityStatus.ResolvedValid ||
            finalStatus == LibLifecycleStorage.IdentityStatus.ResolvedInvalid,
            "Final status must be Resolved*"
        );
        LibLifecycleStorage.Layout storage l = LibLifecycleStorage.layout();
        LibLifecycleStorage.ActionRecord storage rec = l.actionById[actionId];
        require(rec.actionId != 0, "Action not found");
        require(rec.identityStatus == LibLifecycleStorage.IdentityStatus.Disputed, "Action not disputed");

        rec.identityStatus = finalStatus;
        rec.arbiter = msg.sender;

        if (finalStatus == LibLifecycleStorage.IdentityStatus.ResolvedInvalid) {
            l.invalidGovernanceActionCount[rec.tokenId] += 1;
            if (rec.toState > l.highestRepudiatedToState[rec.tokenId]) {
                l.highestRepudiatedToState[rec.tokenId] = rec.toState;
            }
        }

        emit LifecycleEvents.ActionResolved(actionId, rec.tokenId, finalStatus, msg.sender, block.timestamp);
    }

    function resolveDisputeQuorum(
        uint256 actionId,
        LibLifecycleStorage.IdentityStatus finalStatus,
        address signer1,
        bytes calldata sig1,
        address signer2,
        bytes calldata sig2
    ) external {
        require(
            finalStatus == LibLifecycleStorage.IdentityStatus.ResolvedValid ||
            finalStatus == LibLifecycleStorage.IdentityStatus.ResolvedInvalid,
            "Final status must be Resolved*"
        );
        LibLifecycleStorage.Layout storage l = LibLifecycleStorage.layout();
        LibLifecycleStorage.ActionRecord storage rec = l.actionById[actionId];
        require(rec.actionId != 0, "Action not found");
        require(rec.identityStatus == LibLifecycleStorage.IdentityStatus.Disputed, "Action not disputed");

        // (1) Signature verification.
        bytes32 digest = keccak256(
            abi.encodePacked(
                "SMARTPanelVote",
                actionId,
                uint8(finalStatus),
                block.chainid,
                address(this)
            )
        );
        bytes32 ethDigest = ECDSA.toEthSignedMessageHash(digest);
        require(ECDSA.recover(ethDigest, sig1) == signer1, "Invalid sig1");
        require(ECDSA.recover(ethDigest, sig2) == signer2, "Invalid sig2");

        // (2) Distinctness.
        require(signer1 != signer2, "Panel members must differ");

        // (3) Role-class separation: signer1 = Reviewer (claim type 2),
        //     signer2 = Publisher (claim type 3).
        require(
            l.identityRegistry.hasActiveClaim(signer1, 2),
            "signer1 needs active Reviewer claim"
        );
        require(
            l.identityRegistry.hasActiveClaim(signer2, 3),
            "signer2 needs active Publisher claim"
        );

        // (4) Self-disqualification.
        address creator = l.modelCards[rec.tokenId].creator;
        require(!_panelConflict(rec, signer1, creator), "signer1 conflict-of-interest");
        require(!_panelConflict(rec, signer2, creator), "signer2 conflict-of-interest");

        rec.identityStatus = finalStatus;
        rec.arbiter = address(this);
        rec.panelMember1 = signer1;
        rec.panelMember2 = signer2;

        if (finalStatus == LibLifecycleStorage.IdentityStatus.ResolvedInvalid) {
            l.invalidGovernanceActionCount[rec.tokenId] += 1;
            if (rec.toState > l.highestRepudiatedToState[rec.tokenId]) {
                l.highestRepudiatedToState[rec.tokenId] = rec.toState;
            }
        }

        emit LifecycleEvents.ActionResolvedByQuorum(
            actionId, rec.tokenId, finalStatus, signer1, signer2, block.timestamp
        );
    }

    function _panelConflict(
        LibLifecycleStorage.ActionRecord storage rec,
        address candidate,
        address creator
    ) private view returns (bool) {
        if (rec.challenger == candidate) return true;
        if (creator == candidate) return true;
        LibLifecycleStorage.Layout storage l = LibLifecycleStorage.layout();
        uint256[] storage ids = l.actionsForToken[rec.tokenId];
        for (uint256 i = 0; i < ids.length; i++) {
            if (l.actionById[ids[i]].actor == candidate) return true;
        }
        return false;
    }

    function panelVoteDigest(
        uint256 actionId,
        LibLifecycleStorage.IdentityStatus finalStatus
    ) external view returns (bytes32) {
        return keccak256(
            abi.encodePacked(
                "SMARTPanelVote",
                actionId,
                uint8(finalStatus),
                block.chainid,
                address(this)
            )
        );
    }
}
