// SPDX-License-Identifier: MIT
pragma solidity ^0.8.27;

import "@openzeppelin/contracts/access/AccessControl.sol";

contract SMARTVersionRegistry is AccessControl {
    // ============== Roles ==============

    bytes32 public constant LIFECYCLE_ROLE = keccak256("LIFECYCLE_ROLE");

    bytes32 public constant VERSION_ARBITER_ROLE = keccak256("VERSION_ARBITER_ROLE");

    // ============== Enums ==============

    enum Relation {
        Patch,          // bug fix, no behaviour change
        Recalibration,  // probability outputs adjusted, decision boundary unchanged
        Retrain,        // new training data, same architecture
        Reformulation,  // architecture / feature change, same indication
        Reindication,   // same model, new clinical use — typically warrants a NEW line
        Withdrawal      // version is no longer recommended; line continues
    }

    enum EnvelopeStatus {
        Asserted,       // initial state at mint
        Disputed,       // challenged within the window
        Upheld,         // arbiter ruled the claim valid
        Repudiated      // arbiter ruled the claim invalid
    }

    // ============== Structs ==============

    struct LineEnvelope {
        bytes32 hash;
        uint64 pinnedAt;
        uint64 updatedAt;       // 0 if never updated
        address pinnedBy;       // line controller at pin time
    }

    struct VersionRecord {
        uint256 tokenId;
        bytes32 nameHash;
        uint256 supersedes;     // 0 for root
        Relation relation;
        bytes32 envelopeHash;   // frozen copy of the line's envelope
        bool withinEnvelope;    // self-attested at mint
        EnvelopeStatus envelopeStatus;
        uint64 mintedAt;
        address mintedBy;
        // dispute provenance (set on challenge / resolve)
        address challenger;
        uint64 challengedAt;
        address arbiter;
        uint64 resolvedAt;
    }

    // ============== State ==============

    mapping(bytes32 => LineEnvelope) public envelopeOf;

    mapping(uint256 => VersionRecord) public versions;

    mapping(bytes32 => uint256[]) public versionsOfLine;

    uint64 public challengeWindowSeconds = 90 days;

    uint256 public totalVersions;

    // ============== Events ==============

    event EnvelopePinned(bytes32 indexed nameHash, bytes32 envelopeHash, address indexed pinnedBy);
    event EnvelopeUpdated(bytes32 indexed nameHash, bytes32 oldHash, bytes32 newHash, address indexed updatedBy);

    event VersionMinted(
        uint256 indexed tokenId,
        bytes32 indexed nameHash,
        uint256 supersedes,
        Relation relation,
        bytes32 envelopeHash,
        bool withinEnvelope,
        address indexed mintedBy
    );

    event EnvelopeChallenged(uint256 indexed tokenId, address indexed challenger, string reason);
    event EnvelopeResolved(uint256 indexed tokenId, EnvelopeStatus finalStatus, address indexed arbiter);

    event ChallengeWindowChanged(uint64 previous, uint64 next);

    constructor() {
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
        _grantRole(VERSION_ARBITER_ROLE, msg.sender);
    }

    // ============== Admin ==============

    function setChallengeWindow(uint64 newWindow) external onlyRole(DEFAULT_ADMIN_ROLE) {
        emit ChallengeWindowChanged(challengeWindowSeconds, newWindow);
        challengeWindowSeconds = newWindow;
    }

    // ============== Envelope ==============

    function pinEnvelope(bytes32 nameHash, bytes32 envelopeHash, address pinnedBy)
        external
        onlyRole(LIFECYCLE_ROLE)
    {
        require(nameHash != bytes32(0), "Name hash required");
        require(pinnedBy != address(0), "Pinner required");

        LineEnvelope storage env = envelopeOf[nameHash];
        if (env.pinnedAt == 0) {
            env.hash = envelopeHash;
            env.pinnedAt = uint64(block.timestamp);
            env.pinnedBy = pinnedBy;
            emit EnvelopePinned(nameHash, envelopeHash, pinnedBy);
        } else {
            require(env.pinnedBy == pinnedBy, "Envelope pinned by different controller");
            // Same hash from same pinner: idempotent no-op.
            require(env.hash == envelopeHash, "Use updateEnvelope to change a pinned envelope");
        }
    }

    function updateEnvelope(bytes32 nameHash, bytes32 newHash, address updatedBy)
        external
        onlyRole(LIFECYCLE_ROLE)
    {
        LineEnvelope storage env = envelopeOf[nameHash];
        require(env.pinnedAt != 0, "Envelope not pinned");
        require(env.pinnedBy == updatedBy, "Only the original pinner may update");
        bytes32 oldHash = env.hash;
        env.hash = newHash;
        env.updatedAt = uint64(block.timestamp);
        emit EnvelopeUpdated(nameHash, oldHash, newHash, updatedBy);
    }

    // ============== Version mint ==============

    function mintVersion(
        uint256 tokenId,
        bytes32 nameHash,
        uint256 supersedes,
        Relation relation,
        bool withinEnvelope,
        address mintedBy
    )
        external
        onlyRole(LIFECYCLE_ROLE)
    {
        require(tokenId != 0, "Token id required");
        require(nameHash != bytes32(0), "Name hash required");
        require(versions[tokenId].tokenId == 0, "Version already recorded");

        uint256[] storage line = versionsOfLine[nameHash];
        if (line.length == 0) {
            require(supersedes == 0, "First version cannot supersede");
        } else {
            require(supersedes != 0, "Non-first version must supersede");
            require(versions[supersedes].nameHash == nameHash, "Predecessor not in this line");
        }

        bytes32 envHash = envelopeOf[nameHash].hash;
        if (withinEnvelope) {
            require(envHash != bytes32(0), "Cannot claim withinEnvelope without a pinned envelope");
        }

        versions[tokenId] = VersionRecord({
            tokenId: tokenId,
            nameHash: nameHash,
            supersedes: supersedes,
            relation: relation,
            envelopeHash: envHash,
            withinEnvelope: withinEnvelope,
            envelopeStatus: EnvelopeStatus.Asserted,
            mintedAt: uint64(block.timestamp),
            mintedBy: mintedBy,
            challenger: address(0),
            challengedAt: 0,
            arbiter: address(0),
            resolvedAt: 0
        });
        line.push(tokenId);
        totalVersions += 1;

        emit VersionMinted(
            tokenId,
            nameHash,
            supersedes,
            relation,
            envHash,
            withinEnvelope,
            mintedBy
        );
    }

    // ============== Dispute path ==============

    function challengeEnvelope(uint256 tokenId, string calldata reason) external {
        VersionRecord storage rec = versions[tokenId];
        require(rec.tokenId != 0, "Version not found");
        require(rec.withinEnvelope, "Cannot challenge a withinEnvelope=false claim");
        require(rec.envelopeStatus == EnvelopeStatus.Asserted, "Already disputed or resolved");
        require(
            challengeWindowSeconds == 0 ||
            block.timestamp <= rec.mintedAt + challengeWindowSeconds,
            "Challenge window closed"
        );

        rec.envelopeStatus = EnvelopeStatus.Disputed;
        rec.challenger = msg.sender;
        rec.challengedAt = uint64(block.timestamp);

        emit EnvelopeChallenged(tokenId, msg.sender, reason);
    }

    function resolveEnvelope(uint256 tokenId, EnvelopeStatus finalStatus)
        external
        onlyRole(VERSION_ARBITER_ROLE)
    {
        require(
            finalStatus == EnvelopeStatus.Upheld || finalStatus == EnvelopeStatus.Repudiated,
            "Final status must be Upheld or Repudiated"
        );
        VersionRecord storage rec = versions[tokenId];
        require(rec.tokenId != 0, "Version not found");
        require(rec.envelopeStatus == EnvelopeStatus.Disputed, "Not disputed");

        rec.envelopeStatus = finalStatus;
        rec.arbiter = msg.sender;
        rec.resolvedAt = uint64(block.timestamp);

        emit EnvelopeResolved(tokenId, finalStatus, msg.sender);
    }

    // ============== Views ==============

    function versionOf(uint256 tokenId) external view returns (VersionRecord memory) {
        return versions[tokenId];
    }

    function lineageOf(bytes32 nameHash) external view returns (uint256[] memory) {
        return versionsOfLine[nameHash];
    }

    function envelopeFor(bytes32 nameHash) external view returns (LineEnvelope memory) {
        return envelopeOf[nameHash];
    }

    function lineageLength(bytes32 nameHash) external view returns (uint256) {
        return versionsOfLine[nameHash].length;
    }

    function isDisputed(uint256 tokenId) external view returns (bool) {
        return versions[tokenId].envelopeStatus == EnvelopeStatus.Disputed;
    }

    function relationName(Relation r) external pure returns (string memory) {
        if (r == Relation.Patch)         return "Patch";
        if (r == Relation.Recalibration) return "Recalibration";
        if (r == Relation.Retrain)       return "Retrain";
        if (r == Relation.Reformulation) return "Reformulation";
        if (r == Relation.Reindication)  return "Reindication";
        if (r == Relation.Withdrawal)    return "Withdrawal";
        return "Unknown";
    }
}
