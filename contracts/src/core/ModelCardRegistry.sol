// SPDX-License-Identifier: MIT
pragma solidity ^0.8.30;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/access/AccessControl.sol";

interface IModelCardSBT {
    struct CardMeta {
        bytes32 cardHash;
        string cid;
        string modelVersion;
        string runId;
        string schemaVersion;
        address issuer;
        uint64 issuedAt;
        uint256 supersedes;
    }

    function cardMeta(uint256 tokenId) external view returns (CardMeta memory);
}

interface IIdentityRegistry {
    function isIssuer(address issuer) external view returns (bool);
}

contract ModelCardRegistry is Ownable, AccessControl {
    bytes32 public constant REGISTRAR_ROLE = keccak256("REGISTRAR_ROLE");
    bytes32 public constant AUDITOR_ROLE = keccak256("AUDITOR_ROLE");

    struct Registration {
        address sbtContract;
        uint256 tokenId;
        string modelVersion;
        string cid;
        address issuer;
        uint64 registeredAt;
        uint256 supersedesTokenId;
    }

    // modelId hashed -> registration
    mapping(bytes32 => Registration) public registrations;
    IIdentityRegistry public identityRegistry;

    event Registered(bytes32 indexed modelIdHash, uint256 indexed tokenId, string modelVersion, string cid, address issuer);
    event Updated(bytes32 indexed modelIdHash, uint256 indexed tokenId, string modelVersion, string cid, address issuer);

    constructor(address identityRegistry_) {
        identityRegistry = IIdentityRegistry(identityRegistry_);
        _grantRole(DEFAULT_ADMIN_ROLE, _msgSender());
        _grantRole(REGISTRAR_ROLE, _msgSender());
    }

    function setIdentityRegistry(address addr) external onlyOwner {
        identityRegistry = IIdentityRegistry(addr);
    }

    function _checkIssuer(address issuer) internal view {
        require(identityRegistry.isIssuer(issuer), "issuer not trusted");
    }

    function grantRegistrar(address account) external onlyOwner {
        _grantRole(REGISTRAR_ROLE, account);
    }

    function revokeRegistrar(address account) external onlyOwner {
        _revokeRole(REGISTRAR_ROLE, account);
    }

    function grantAuditor(address account) external onlyOwner {
        _grantRole(AUDITOR_ROLE, account);
    }

    function revokeAuditor(address account) external onlyOwner {
        _revokeRole(AUDITOR_ROLE, account);
    }

    function register(
        string calldata modelId,    // e.g., "my-model" or UUID
        address sbtContract,
        uint256 tokenId
    ) external {
        require(hasRole(REGISTRAR_ROLE, _msgSender()), "not registrar");
        bytes32 key = keccak256(bytes(modelId));
        require(registrations[key].tokenId == 0, "already registered");

        IModelCardSBT.CardMeta memory meta = IModelCardSBT(sbtContract).cardMeta(tokenId);
        _checkIssuer(meta.issuer);

        registrations[key] = Registration({
            sbtContract: sbtContract,
            tokenId: tokenId,
            modelVersion: meta.modelVersion,
            cid: meta.cid,
            issuer: meta.issuer,
            registeredAt: uint64(block.timestamp),
            supersedesTokenId: meta.supersedes
        });
        emit Registered(key, tokenId, meta.modelVersion, meta.cid, meta.issuer);
    }

    function update(
        string calldata modelId,
        address sbtContract,
        uint256 tokenId
    ) external {
        require(hasRole(REGISTRAR_ROLE, _msgSender()), "not registrar");
        bytes32 key = keccak256(bytes(modelId));
        require(registrations[key].tokenId != 0, "not registered");

        IModelCardSBT.CardMeta memory meta = IModelCardSBT(sbtContract).cardMeta(tokenId);
        _checkIssuer(meta.issuer);

        registrations[key] = Registration({
            sbtContract: sbtContract,
            tokenId: tokenId,
            modelVersion: meta.modelVersion,
            cid: meta.cid,
            issuer: meta.issuer,
            registeredAt: uint64(block.timestamp),
            supersedesTokenId: meta.supersedes
        });
        emit Updated(key, tokenId, meta.modelVersion, meta.cid, meta.issuer);
    }

    function getRegistration(string calldata modelId) external view returns (Registration memory) {
        return registrations[keccak256(bytes(modelId))];
    }

    function supportsInterface(bytes4 interfaceId) public view override returns (bool) {
        return interfaceId == type(IAccessControl).interfaceId || super.supportsInterface(interfaceId);
    }
}
