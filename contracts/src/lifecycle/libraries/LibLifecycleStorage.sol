// SPDX-License-Identifier: MIT
pragma solidity ^0.8.27;

import "../../core/SMARTIdentityRegistry.sol";
import "../../core/SMARTNameRegistry.sol";
import "../../core/SMARTVersionRegistry.sol";

interface ISMARTModelCardSBT {
    function mint(
        address to,
        bytes32 cardHash,
        string calldata cid,
        string calldata modelVersion,
        string calldata runId,
        string calldata schemaVersion,
        uint256 supersedesTokenId,
        string calldata tokenURI_
    ) external returns (uint256);
}

library LibLifecycleStorage {
    bytes32 internal constant STORAGE_POSITION =
        keccak256("smart.lifecycle.storage.v1");

    enum Status {
        Created,
        InEvaluation,
        Validated,
        Rejected,
        RevisionRequested,
        Revised,
        Published,
        Deprecated
    }

    enum TransitionType {
        Create,
        Submit,
        Validate,
        Reject,
        RequestRevision,
        Revise,
        Publish,
        Deprecate,
        AdminPublish,
        AdminDeprecate
    }

    enum IdentityStatus {
        Bound,
        UnboundOptimistic,
        UnboundMissing,
        Disputed,
        ResolvedValid,
        ResolvedInvalid
    }

    enum RepudiationReason {
        NoClaim,
        ExpiredClaim,
        RevokedClaim,
        InvalidIssuer,
        SubjectMismatch,
        ContextMismatch,
        SignatureInvalid,
        RegistryInconsistency
    }

    struct ModelCard {
        uint256 tokenId;
        address creator;
        string metadataURI;
        bytes32 contentHash;
        Status status;
        uint256 createdAt;
        uint256 lastUpdated;
        string revisionNotes;
        address lastModifiedBy;
        bool isActive;
        uint256 version;
        uint256 revisionCount;
    }

    struct RevisionRecord {
        uint256 revisionNumber;
        string previousMetadataURI;
        bytes32 previousContentHash;
        string newMetadataURI;
        bytes32 newContentHash;
        string revisionNotes;
        address revisedBy;
        uint256 timestamp;
    }

    struct ActionRecord {
        uint256 actionId;
        uint256 tokenId;
        address actor;
        uint8 fromState;
        uint8 toState;
        uint8 transitionType;
        bytes32 contentHash;
        bytes32 claimRef;
        bytes32 issuerRef;
        bytes32 contextRef;
        uint64 timestamp;
        uint64 blockNumber;
        uint64 registryVersion;
        IdentityStatus identityStatus;
        RepudiationReason challengeReason;
        address arbiter;
        address panelMember1;
        address panelMember2;
        address challenger;
    }

    struct Layout {
        // Token-id counter (replaces OpenZeppelin Counters.Counter
        // — same semantics: monotonically increasing _value).
        uint256 tokenIdCounter;
        // tokenId → ModelCard
        mapping(uint256 => ModelCard) modelCards;
        // tokenId → status sequence (revision trace)
        mapping(uint256 => Status[]) statusHistory;
        // tokenId → revision history
        mapping(uint256 => RevisionRecord[]) revisionHistory;
        // External registries
        SMARTIdentityRegistry identityRegistry;
        SMARTNameRegistry nameRegistry;
        SMARTVersionRegistry versionRegistry;
        // Default challenge window
        uint64 challengeWindowSeconds;
        // Per-transition strict-mode flags
        mapping(uint8 => bool) requireIdentityForTransition;
        // Action ledger
        uint256 nextActionId;
        mapping(uint256 => ActionRecord) actionById;
        mapping(uint256 => uint256[]) actionsForToken;
        // Per-token disputed-action counters
        mapping(uint256 => uint32) invalidGovernanceActionCount;
        mapping(uint256 => uint8) highestRepudiatedToState;
        // Optional SBT contract
        ISMARTModelCardSBT sbtContract;
        // tokenId → SBT tokenId
        mapping(uint256 => uint256) lifecycleToSBT;
        // OpenZeppelin's ERC721 storage replicated here so the LifecycleNFT
        // can implement the interface without inheriting OZ's contract
        // (which is too large to deploy as part of the diamond).
        // Layouts:
        //   _owners: tokenId → owner
        //   _balances: owner → balance
        //   _name, _symbol: ERC-721 metadata
        //   _tokenApprovals: tokenId → approved address (always 0 for soulbound)
        //   _operatorApprovals: owner → operator → bool (always false for soulbound)
        mapping(uint256 => address) erc721Owners;
        mapping(address => uint256) erc721Balances;
        string erc721Name;
        string erc721Symbol;
        mapping(uint256 => address) erc721TokenApprovals;
        mapping(address => mapping(address => bool)) erc721OperatorApprovals;
        // OpenZeppelin AccessControl uses:
        //   _roles[role].members[account] = bool
        //   _roles[role].adminRole = bytes32
        // Replicated here as flat mappings for simplicity.
        mapping(bytes32 => mapping(address => bool)) roleMembers;
        mapping(bytes32 => bytes32) roleAdmin;
        bool initialized;
    }

    function layout() internal pure returns (Layout storage l) {
        bytes32 position = STORAGE_POSITION;
        assembly {
            l.slot := position
        }
    }
}
