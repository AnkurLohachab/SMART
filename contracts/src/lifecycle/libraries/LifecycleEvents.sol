// SPDX-License-Identifier: MIT
pragma solidity ^0.8.27;

import "./LibLifecycleStorage.sol";

library LifecycleEvents {

    event ModelCardCreated(
        uint256 indexed tokenId,
        address indexed creator,
        string metadataURI,
        bytes32 contentHash,
        uint256 timestamp
    );

    event ModelCardSubmitted(
        uint256 indexed tokenId,
        address indexed initiator,
        uint256 timestamp
    );

    event ModelCardValidated(
        uint256 indexed tokenId,
        address indexed validator,
        uint256 timestamp
    );

    event ModelCardRejected(
        uint256 indexed tokenId,
        address indexed rejector,
        string reason,
        uint256 timestamp
    );

    event RevisionRequested(
        uint256 indexed tokenId,
        address indexed requester,
        string feedback,
        uint256 timestamp
    );

    event HTAAttested(
        uint256 indexed tokenId,
        address indexed assessor,
        uint8 verdict,
        bytes32 reportHash,
        uint256 timestamp
    );

    event ModelCardRevised(
        uint256 indexed tokenId,
        address indexed revisor,
        string newMetadataURI,
        bytes32 newContentHash,
        string revisionNotes,
        uint256 timestamp
    );

    event RevisionHistoryRecorded(
        uint256 indexed tokenId,
        uint256 indexed revisionNumber,
        bytes32 previousContentHash,
        bytes32 newContentHash,
        address indexed revisedBy,
        uint256 timestamp
    );

    event ModelCardPublished(
        uint256 indexed tokenId,
        address indexed publisher,
        uint256 timestamp
    );

    event ModelCardDeprecated(
        uint256 indexed tokenId,
        address indexed publisher,
        string reason,
        uint256 timestamp
    );

    event AdminOverride(
        uint256 indexed tokenId,
        address indexed admin,
        string action,
        string justification,
        uint256 timestamp
    );

    event StatusChanged(
        uint256 indexed tokenId,
        LibLifecycleStorage.Status oldStatus,
        LibLifecycleStorage.Status newStatus,
        address indexed changedBy,
        uint256 timestamp
    );

    event ProvenanceSBTMinted(
        uint256 indexed lifecycleTokenId,
        uint256 indexed sbtTokenId,
        bytes32 contentHash,
        address indexed recipient,
        uint256 timestamp
    );

    event SBTContractUpdated(
        address indexed previousContract,
        address indexed newContract,
        uint256 timestamp
    );

    event BoundAction(
        uint256 indexed actionId,
        uint256 indexed tokenId,
        address indexed actor,
        uint8 fromState,
        uint8 toState,
        uint8 transitionType,
        bytes32 contentHash,
        bytes32 claimRef,
        bytes32 issuerRef,
        bytes32 contextRef,
        LibLifecycleStorage.IdentityStatus identityStatus,
        uint256 timestamp
    );

    event ActionChallenged(
        uint256 indexed actionId,
        uint256 indexed tokenId,
        address indexed challenger,
        LibLifecycleStorage.RepudiationReason reason,
        uint256 timestamp
    );

    event ActionResolved(
        uint256 indexed actionId,
        uint256 indexed tokenId,
        LibLifecycleStorage.IdentityStatus finalStatus,
        address indexed arbiter,
        uint256 timestamp
    );

    event ActionResolvedByQuorum(
        uint256 indexed actionId,
        uint256 indexed tokenId,
        LibLifecycleStorage.IdentityStatus finalStatus,
        address signer1,
        address signer2,
        uint256 timestamp
    );

    event IdentityRegistryUpdated(
        address indexed previousRegistry,
        address indexed newRegistry,
        uint256 timestamp
    );

    event StrictModeChanged(
        uint8 indexed transitionType,
        bool required,
        uint256 timestamp
    );

    event ChallengeWindowChanged(
        uint64 previousSeconds,
        uint64 newSeconds,
        uint256 timestamp
    );

    event Transfer(address indexed from, address indexed to, uint256 indexed tokenId);
    event Approval(address indexed owner, address indexed approved, uint256 indexed tokenId);
    event ApprovalForAll(address indexed owner, address indexed operator, bool approved);

    event Locked(uint256 tokenId);
}
