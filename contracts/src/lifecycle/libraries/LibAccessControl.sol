// SPDX-License-Identifier: MIT
pragma solidity ^0.8.27;

import "./LibLifecycleStorage.sol";

library LibAccessControl {
    bytes32 internal constant DEFAULT_ADMIN_ROLE = 0x00;
    bytes32 internal constant DEVELOPER_ROLE = keccak256("DEVELOPER_ROLE");
    bytes32 internal constant AUTHENTICATOR_ROLE = keccak256("AUTHENTICATOR_ROLE");
    bytes32 internal constant PUBLISHER_ROLE = keccak256("PUBLISHER_ROLE");
    bytes32 internal constant ADMIN_ROLE = keccak256("ADMIN_ROLE");
    bytes32 internal constant IDENTITY_ARBITER_ROLE = keccak256("IDENTITY_ARBITER_ROLE");

    event RoleGranted(bytes32 indexed role, address indexed account, address indexed sender);
    event RoleRevoked(bytes32 indexed role, address indexed account, address indexed sender);
    event RoleAdminChanged(bytes32 indexed role, bytes32 indexed previousAdminRole, bytes32 indexed newAdminRole);

    function hasRole(bytes32 role, address account) internal view returns (bool) {
        return LibLifecycleStorage.layout().roleMembers[role][account];
    }

    function checkRole(bytes32 role) internal view {
        checkRole(role, msg.sender);
    }

    function checkRole(bytes32 role, address account) internal view {
        if (!hasRole(role, account)) {
            revert(
                string.concat(
                    "AccessControl: account ",
                    toAsciiString(account),
                    " is missing role ",
                    toHexString(uint256(role), 32)
                )
            );
        }
    }

    function getRoleAdmin(bytes32 role) internal view returns (bytes32) {
        return LibLifecycleStorage.layout().roleAdmin[role];
    }

    function setRoleAdmin(bytes32 role, bytes32 adminRole) internal {
        bytes32 previous = LibLifecycleStorage.layout().roleAdmin[role];
        LibLifecycleStorage.layout().roleAdmin[role] = adminRole;
        emit RoleAdminChanged(role, previous, adminRole);
    }

    function _grantRole(bytes32 role, address account) internal {
        if (!hasRole(role, account)) {
            LibLifecycleStorage.layout().roleMembers[role][account] = true;
            emit RoleGranted(role, account, msg.sender);
        }
    }

    function _revokeRole(bytes32 role, address account) internal {
        if (hasRole(role, account)) {
            LibLifecycleStorage.layout().roleMembers[role][account] = false;
            emit RoleRevoked(role, account, msg.sender);
        }
    }

    function toAsciiString(address x) private pure returns (string memory) {
        bytes memory s = new bytes(42);
        s[0] = "0";
        s[1] = "x";
        for (uint256 i = 0; i < 20; i++) {
            uint8 b = uint8(uint160(x) / (2 ** (8 * (19 - i))));
            uint8 hi = b / 16;
            uint8 lo = b - 16 * hi;
            s[2 + 2 * i] = nibble(hi);
            s[3 + 2 * i] = nibble(lo);
        }
        return string(s);
    }

    function toHexString(uint256 value, uint256 length) private pure returns (string memory) {
        bytes memory buffer = new bytes(2 * length + 2);
        buffer[0] = "0";
        buffer[1] = "x";
        for (uint256 i = 2 * length + 1; i > 1; --i) {
            buffer[i] = nibble(uint8(value & 0xf));
            value >>= 4;
        }
        return string(buffer);
    }

    function nibble(uint8 b) private pure returns (bytes1) {
        return bytes1(b < 10 ? b + 0x30 : b + 0x57);
    }
}
