// SPDX-License-Identifier: MIT
pragma solidity ^0.8.27;

import "@openzeppelin/contracts/access/AccessControl.sol";

contract SMARTNameRegistry is AccessControl {
    bytes32 public constant LIFECYCLE_ROLE = keccak256("LIFECYCLE_ROLE");

    struct NameRecord {
        bytes32 nameHash;          // redundant but cheap and useful for events
        bytes alias_;              // shortest non-colliding alias
        address controller;        // who can mint versions under this name
        uint64 firstClaimedAt;
        uint64 lastVersionAt;
        uint256 versionCount;
        // tokenIds stored separately — variable-length array
    }

    mapping(bytes32 => NameRecord) public records;

    mapping(bytes => bytes32) public aliasToNameHash;

    mapping(bytes32 => uint256[]) public versionsOf;

    mapping(uint256 => bytes32) public tokenIdToNameHash;

    uint256 public totalNames;

    event NameClaimed(
        bytes32 indexed nameHash,
        bytes alias_,
        address indexed controller,
        uint8 aliasLength
    );

    event VersionRecorded(
        bytes32 indexed nameHash,
        uint256 indexed tokenId,
        uint256 versionIndex
    );

    constructor() {
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
    }

    // ============== Mutators ==============

    function claimName(string calldata name, address controller)
        external
        onlyRole(LIFECYCLE_ROLE)
        returns (bytes memory aliasOut)
    {
        require(bytes(name).length > 0, "Name required");
        require(controller != address(0), "Controller required");

        bytes32 fullHash = keccak256(bytes(name));
        NameRecord storage rec = records[fullHash];

        // Idempotent for same-controller re-claim
        if (rec.firstClaimedAt != 0) {
            require(rec.controller == controller, "Name owned by other controller");
            return rec.alias_;
        }

        // Try increasing alias lengths: 8, 12, 16
        bytes memory candidate;
        uint8 length;
        for (uint8 lengthIdx = 0; lengthIdx < 3; lengthIdx++) {
            length = uint8(8 + lengthIdx * 4);
            candidate = _truncate(fullHash, length);
            bytes32 occupant = aliasToNameHash[candidate];
            if (occupant == bytes32(0)) {
                break; // free
            }
            // collision: occupant is a different name; try a longer alias
            require(lengthIdx < 2, "Name registry: 16-byte collision (impossibly unlucky)");
        }

        aliasToNameHash[candidate] = fullHash;
        records[fullHash] = NameRecord({
            nameHash: fullHash,
            alias_: candidate,
            controller: controller,
            firstClaimedAt: uint64(block.timestamp),
            lastVersionAt: 0,
            versionCount: 0
        });
        totalNames++;

        emit NameClaimed(fullHash, candidate, controller, length);
        return candidate;
    }

    function recordVersion(string calldata name, uint256 tokenId)
        external
        onlyRole(LIFECYCLE_ROLE)
    {
        bytes32 fullHash = keccak256(bytes(name));
        NameRecord storage rec = records[fullHash];
        require(rec.firstClaimedAt != 0, "Name not claimed");
        require(tokenId != 0, "Token id required");
        require(tokenIdToNameHash[tokenId] == bytes32(0), "Token already named");

        versionsOf[fullHash].push(tokenId);
        tokenIdToNameHash[tokenId] = fullHash;
        rec.versionCount += 1;
        rec.lastVersionAt = uint64(block.timestamp);

        emit VersionRecorded(fullHash, tokenId, rec.versionCount - 1);
    }

    // ============== Views ==============

    function aliasOf(string calldata name) external view returns (bytes memory) {
        bytes32 fullHash = keccak256(bytes(name));
        return records[fullHash].alias_;
    }

    function nameHashOfAlias(bytes calldata aliasIn) external view returns (bytes32) {
        return aliasToNameHash[aliasIn];
    }

    function tokenIdsOfName(string calldata name) external view returns (uint256[] memory) {
        return versionsOf[keccak256(bytes(name))];
    }

    function tokenIdsOfHash(bytes32 nameHash) external view returns (uint256[] memory) {
        return versionsOf[nameHash];
    }

    function nameHashOfToken(uint256 tokenId) external view returns (bytes32) {
        return tokenIdToNameHash[tokenId];
    }

    function controllerOf(string calldata name) external view returns (address) {
        return records[keccak256(bytes(name))].controller;
    }

    function recordOf(string calldata name) external view returns (NameRecord memory) {
        return records[keccak256(bytes(name))];
    }

    function resolve(bytes calldata aliasIn)
        external
        view
        returns (bytes32 nameHash, NameRecord memory rec)
    {
        bytes32 hash = aliasToNameHash[aliasIn];
        if (hash != bytes32(0)) {
            return (hash, records[hash]);
        }
        return (bytes32(0), records[bytes32(0)]);
    }

    // ============== Internal ==============

    function _truncate(bytes32 source, uint8 length) internal pure returns (bytes memory out) {
        require(length == 8 || length == 12 || length == 16, "Invalid alias length");
        out = new bytes(length);
        for (uint8 i = 0; i < length; i++) {
            out[i] = source[i];
        }
    }
}
