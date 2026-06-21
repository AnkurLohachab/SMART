// SPDX-License-Identifier: MIT
pragma solidity ^0.8.27;

enum SMARTRole {
    Reader,        // 0 - Read-only access to model cards
    AIDeveloper,   // 1 - Model card creation and revision
    Authenticator, // 2 - Quality control, validation, rejection
    Publisher,     // 3 - Release management, publish/deprecate
    Admin          // 4 - System administration
}

library SMARTRoleLibrary {
    function canCreateModelCard(SMARTRole role) internal pure returns (bool) {
        return role == SMARTRole.AIDeveloper || role == SMARTRole.Admin;
    }

    function canValidate(SMARTRole role) internal pure returns (bool) {
        return role == SMARTRole.Authenticator || role == SMARTRole.Admin;
    }

    function canPublish(SMARTRole role) internal pure returns (bool) {
        return role == SMARTRole.Publisher || role == SMARTRole.Admin;
    }

    function canDeprecate(SMARTRole role) internal pure returns (bool) {
        return role == SMARTRole.Publisher || role == SMARTRole.Admin;
    }

    function isAdmin(SMARTRole role) internal pure returns (bool) {
        return role == SMARTRole.Admin;
    }

    function roleName(SMARTRole role) internal pure returns (string memory) {
        if (role == SMARTRole.Reader) return "Reader";
        if (role == SMARTRole.AIDeveloper) return "AI Developer";
        if (role == SMARTRole.Authenticator) return "Authenticator";
        if (role == SMARTRole.Publisher) return "Publisher";
        if (role == SMARTRole.Admin) return "Admin";
        return "Unknown";
    }
}
