// SPDX-License-Identifier: MIT
pragma solidity ^0.8.30;

import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";

contract SMARTIdentityRegistry is AccessControl {
    using ECDSA for bytes32;

    // ============== Constants ==============

    bytes32 public constant REGISTRY_ADMIN_ROLE = keccak256("REGISTRY_ADMIN_ROLE");
    bytes32 public constant ISSUER_MANAGER_ROLE = keccak256("ISSUER_MANAGER_ROLE");

    // Claim type constants (ERC-735 inspired)
    uint256 public constant CLAIM_TYPE_ISSUER = 1;
    uint256 public constant CLAIM_TYPE_AUTHENTICATOR = 2;
    uint256 public constant CLAIM_TYPE_PUBLISHER = 3;
    uint256 public constant CLAIM_TYPE_INSTITUTION = 4;
    uint256 public constant CLAIM_TYPE_CERTIFICATION = 5;

    // ============== Enums ==============

    enum IssuerType {
        Individual,
        Organization,
        NotifiedBody,
        CertificationBody,
        Government
    }

    // ============== Structs ==============

    struct Issuer {
        bool isActive;
        string name;
        string uri;
        uint256 registeredAt;
        uint256 claimsIssued;
        IssuerType issuerType;
    }

    struct Claim {
        uint256 claimType;
        address issuer;
        bytes signature;
        bytes data;
        string uri;
        uint256 issuedAt;
        uint256 expiresAt;
        bool revoked;
    }

    struct IdentitySnapshot {
        bytes32 claimRef;
        bytes32 issuerRef;
        bytes32 subjectRef;
        bytes32 contextRef;
        uint64 validFrom;
        uint64 validUntil;
        uint64 registryVersion;
    }

    // ============== State Variables ==============

    uint64 public registryVersion;

    mapping(address => Issuer) public issuers;

    address[] public issuerList;

    mapping(address => mapping(bytes32 => Claim)) public claims;

    mapping(address => bytes32[]) public claimIds;

    mapping(address => mapping(uint256 => bytes32[])) public claimsByType;

    // ============== Events ==============

    event IssuerAdded(
        address indexed issuer,
        string name,
        IssuerType issuerType,
        uint256 timestamp
    );

    event IssuerUpdated(
        address indexed issuer,
        string name,
        string uri,
        uint256 timestamp
    );

    event IssuerRemoved(address indexed issuer, uint256 timestamp);

    event IssuerStatusChanged(
        address indexed issuer,
        bool isActive,
        uint256 timestamp
    );

    event ClaimAdded(
        address indexed identity,
        bytes32 indexed claimId,
        uint256 indexed claimType,
        address issuer,
        uint256 expiresAt
    );

    event ClaimRevoked(
        address indexed identity,
        bytes32 indexed claimId,
        address revokedBy,
        uint256 timestamp
    );

    event ClaimRemoved(
        address indexed identity,
        bytes32 indexed claimId,
        uint256 timestamp
    );

    // ============== Constructor ==============

    constructor() {
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
        _grantRole(REGISTRY_ADMIN_ROLE, msg.sender);
        _grantRole(ISSUER_MANAGER_ROLE, msg.sender);
    }

    // ============== Issuer Management ==============

    function addIssuer(
        address issuer,
        string calldata name,
        string calldata uri,
        IssuerType issuerType
    ) external onlyRole(ISSUER_MANAGER_ROLE) {
        require(issuer != address(0), "SMARTIdentityRegistry: invalid address");
        require(!issuers[issuer].isActive, "SMARTIdentityRegistry: issuer exists");
        require(bytes(name).length > 0, "SMARTIdentityRegistry: name required");

        issuers[issuer] = Issuer({
            isActive: true,
            name: name,
            uri: uri,
            registeredAt: block.timestamp,
            claimsIssued: 0,
            issuerType: issuerType
        });

        issuerList.push(issuer);
        registryVersion++;

        emit IssuerAdded(issuer, name, issuerType, block.timestamp);
    }

    function addIssuer(address issuer) external onlyRole(ISSUER_MANAGER_ROLE) {
        require(issuer != address(0), "SMARTIdentityRegistry: invalid address");
        require(!issuers[issuer].isActive, "SMARTIdentityRegistry: issuer exists");

        issuers[issuer] = Issuer({
            isActive: true,
            name: "",
            uri: "",
            registeredAt: block.timestamp,
            claimsIssued: 0,
            issuerType: IssuerType.Individual
        });

        issuerList.push(issuer);
        registryVersion++;

        emit IssuerAdded(issuer, "", IssuerType.Individual, block.timestamp);
    }

    function updateIssuer(
        address issuer,
        string calldata name,
        string calldata uri
    ) external onlyRole(ISSUER_MANAGER_ROLE) {
        require(issuers[issuer].registeredAt > 0, "SMARTIdentityRegistry: not found");

        issuers[issuer].name = name;
        issuers[issuer].uri = uri;

        emit IssuerUpdated(issuer, name, uri, block.timestamp);
    }

    function deactivateIssuer(address issuer) external onlyRole(ISSUER_MANAGER_ROLE) {
        require(issuers[issuer].isActive, "SMARTIdentityRegistry: not active");

        issuers[issuer].isActive = false;
        registryVersion++;

        emit IssuerStatusChanged(issuer, false, block.timestamp);
    }

    function reactivateIssuer(address issuer) external onlyRole(ISSUER_MANAGER_ROLE) {
        require(issuers[issuer].registeredAt > 0, "SMARTIdentityRegistry: not found");
        require(!issuers[issuer].isActive, "SMARTIdentityRegistry: already active");

        issuers[issuer].isActive = true;
        registryVersion++;

        emit IssuerStatusChanged(issuer, true, block.timestamp);
    }

    function removeIssuer(address issuer) external onlyRole(REGISTRY_ADMIN_ROLE) {
        require(issuers[issuer].registeredAt > 0, "SMARTIdentityRegistry: not found");

        delete issuers[issuer];

        // Remove from list
        for (uint256 i = 0; i < issuerList.length; i++) {
            if (issuerList[i] == issuer) {
                issuerList[i] = issuerList[issuerList.length - 1];
                issuerList.pop();
                break;
            }
        }
        registryVersion++;

        emit IssuerRemoved(issuer, block.timestamp);
    }

    // ============== Claim Management ==============

    function addClaim(
        address identity,
        uint256 claimType,
        bytes calldata data,
        string calldata uri,
        uint256 expiresAt,
        bytes calldata signature
    ) external returns (bytes32 claimId) {
        require(issuers[msg.sender].isActive, "SMARTIdentityRegistry: not active issuer");
        require(identity != address(0), "SMARTIdentityRegistry: invalid identity");

        // Generate claim ID
        claimId = keccak256(abi.encodePacked(identity, claimType, msg.sender, block.timestamp));

        // Store claim
        claims[identity][claimId] = Claim({
            claimType: claimType,
            issuer: msg.sender,
            signature: signature,
            data: data,
            uri: uri,
            issuedAt: block.timestamp,
            expiresAt: expiresAt,
            revoked: false
        });

        claimIds[identity].push(claimId);
        claimsByType[identity][claimType].push(claimId);

        // Increment issuer's counter
        issuers[msg.sender].claimsIssued++;

        emit ClaimAdded(identity, claimId, claimType, msg.sender, expiresAt);

        return claimId;
    }

    function revokeClaim(address identity, bytes32 claimId) external {
        Claim storage claim = claims[identity][claimId];
        require(claim.issuer != address(0), "SMARTIdentityRegistry: claim not found");
        require(
            msg.sender == claim.issuer || hasRole(REGISTRY_ADMIN_ROLE, msg.sender),
            "SMARTIdentityRegistry: unauthorized"
        );
        require(!claim.revoked, "SMARTIdentityRegistry: already revoked");

        claim.revoked = true;

        emit ClaimRevoked(identity, claimId, msg.sender, block.timestamp);
    }

    function removeClaim(bytes32 claimId) external {
        Claim storage claim = claims[msg.sender][claimId];
        require(claim.issuer != address(0), "SMARTIdentityRegistry: claim not found");

        delete claims[msg.sender][claimId];

        emit ClaimRemoved(msg.sender, claimId, block.timestamp);
    }

    // ============== View Functions ==============

    function isIssuer(address issuer) external view returns (bool) {
        return issuers[issuer].isActive;
    }

    function getIssuer(address issuer) external view returns (
        bool isActive,
        string memory name,
        string memory uri,
        uint256 registeredAt,
        uint256 claimsIssued,
        IssuerType issuerType
    ) {
        Issuer memory i = issuers[issuer];
        return (i.isActive, i.name, i.uri, i.registeredAt, i.claimsIssued, i.issuerType);
    }

    function getIssuerCount() external view returns (uint256) {
        return issuerList.length;
    }

    function getClaim(address identity, bytes32 claimId) external view returns (
        uint256 claimType,
        address issuer,
        bytes memory signature,
        bytes memory data,
        string memory uri,
        uint256 issuedAt,
        uint256 expiresAt,
        bool revoked
    ) {
        Claim memory c = claims[identity][claimId];
        return (c.claimType, c.issuer, c.signature, c.data, c.uri, c.issuedAt, c.expiresAt, c.revoked);
    }

    function isClaimValid(address identity, bytes32 claimId) external view returns (bool) {
        Claim memory claim = claims[identity][claimId];

        if (claim.issuer == address(0)) return false;
        if (claim.revoked) return false;
        if (claim.expiresAt > 0 && block.timestamp > claim.expiresAt) return false;
        if (!issuers[claim.issuer].isActive) return false;

        return true;
    }

    function getClaimIds(address identity) external view returns (bytes32[] memory) {
        return claimIds[identity];
    }

    function getClaimsByType(
        address identity,
        uint256 claimType
    ) external view returns (bytes32[] memory) {
        return claimsByType[identity][claimType];
    }

    function hasValidClaim(address identity, uint256 claimType) external view returns (bool) {
        bytes32[] memory typeClaimIds = claimsByType[identity][claimType];

        for (uint256 i = 0; i < typeClaimIds.length; i++) {
            Claim memory claim = claims[identity][typeClaimIds[i]];

            if (
                !claim.revoked &&
                (claim.expiresAt == 0 || block.timestamp <= claim.expiresAt) &&
                issuers[claim.issuer].isActive
            ) {
                return true;
            }
        }

        return false;
    }

    function verifyClaimSignature(
        address identity,
        bytes32 claimId
    ) external view returns (bool) {
        Claim memory claim = claims[identity][claimId];
        if (claim.issuer == address(0)) return false;

        bytes32 messageHash = keccak256(
            abi.encodePacked(identity, claim.claimType, claim.data, claim.expiresAt)
        );
        bytes32 ethSignedHash = ECDSA.toEthSignedMessageHash(messageHash);

        address recovered = ECDSA.recover(ethSignedHash, claim.signature);
        return recovered == claim.issuer;
    }

    function hasActiveClaim(address actor, uint256 claimType) external view returns (bool) {
        bytes32[] storage typeIds = claimsByType[actor][claimType];
        for (uint256 i = typeIds.length; i > 0; i--) {
            bytes32 cid = typeIds[i - 1];
            Claim storage c = claims[actor][cid];
            if (
                c.issuer != address(0) &&
                !c.revoked &&
                (c.expiresAt == 0 || block.timestamp <= c.expiresAt) &&
                issuers[c.issuer].isActive
            ) {
                return true;
            }
        }
        return false;
    }

    function snapshotOf(address actor, uint256 requiredClaimType)
        external
        view
        returns (IdentitySnapshot memory)
    {
        bytes32[] storage typeIds = claimsByType[actor][requiredClaimType];
        for (uint256 i = typeIds.length; i > 0; i--) {
            bytes32 cid = typeIds[i - 1];
            Claim storage c = claims[actor][cid];
            if (
                c.issuer != address(0) &&
                !c.revoked &&
                (c.expiresAt == 0 || block.timestamp <= c.expiresAt) &&
                issuers[c.issuer].isActive
            ) {
                bytes32 cref = keccak256(
                    abi.encode(
                        actor,
                        c.claimType,
                        c.issuer,
                        c.data,
                        c.signature,
                        c.issuedAt,
                        c.expiresAt
                    )
                );
                return IdentitySnapshot({
                    claimRef: cref,
                    issuerRef: bytes32(uint256(uint160(c.issuer))),
                    subjectRef: bytes32(uint256(uint160(actor))),
                    contextRef: bytes32(requiredClaimType),
                    validFrom: uint64(c.issuedAt),
                    validUntil: uint64(c.expiresAt),
                    registryVersion: registryVersion
                });
            }
        }
        return IdentitySnapshot({
            claimRef: bytes32(0),
            issuerRef: bytes32(0),
            subjectRef: bytes32(uint256(uint160(actor))),
            contextRef: bytes32(requiredClaimType),
            validFrom: 0,
            validUntil: 0,
            registryVersion: registryVersion
        });
    }
}
