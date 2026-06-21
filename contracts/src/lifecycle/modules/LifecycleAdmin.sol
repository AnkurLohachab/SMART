// SPDX-License-Identifier: MIT
pragma solidity ^0.8.27;

import "../libraries/LibLifecycleStorage.sol";
import "../libraries/LibLifecycleCore.sol";
import "../libraries/LibAccessControl.sol";
import "../libraries/LibRouter.sol";
import "../libraries/LifecycleEvents.sol";

contract LifecycleAdmin {

    function initialize(address admin, string memory name_, string memory symbol_) external {
        LibLifecycleStorage.Layout storage l = LibLifecycleStorage.layout();
        require(!l.initialized, "Already initialized");
        l.initialized = true;

        l.erc721Name = name_;
        l.erc721Symbol = symbol_;
        l.challengeWindowSeconds = 90 days;

        // Wire the role admin chain so DEFAULT_ADMIN_ROLE is the admin of all
        // operational roles (matches OZ defaults).
        LibAccessControl.setRoleAdmin(LibAccessControl.DEVELOPER_ROLE, LibAccessControl.DEFAULT_ADMIN_ROLE);
        LibAccessControl.setRoleAdmin(LibAccessControl.AUTHENTICATOR_ROLE, LibAccessControl.DEFAULT_ADMIN_ROLE);
        LibAccessControl.setRoleAdmin(LibAccessControl.PUBLISHER_ROLE, LibAccessControl.DEFAULT_ADMIN_ROLE);
        LibAccessControl.setRoleAdmin(LibAccessControl.ADMIN_ROLE, LibAccessControl.DEFAULT_ADMIN_ROLE);
        LibAccessControl.setRoleAdmin(LibAccessControl.IDENTITY_ARBITER_ROLE, LibAccessControl.DEFAULT_ADMIN_ROLE);

        LibAccessControl._grantRole(LibAccessControl.DEFAULT_ADMIN_ROLE, admin);
        LibAccessControl._grantRole(LibAccessControl.ADMIN_ROLE, admin);

        // Register ERC-165 / ERC-721 / EIP-5192 / RouterCut / DiamondLoupe
        // interface IDs so the Loupe facet's `supportsInterface` returns true
        // for them.
        LibRouter.RouterStorage storage ds = LibRouter.routerStorage();
        ds.supportedInterfaces[0x01ffc9a7] = true; // ERC-165
        ds.supportedInterfaces[0x80ac58cd] = true; // ERC-721
        ds.supportedInterfaces[0x5b5e139f] = true; // ERC-721 Metadata
        ds.supportedInterfaces[0xb45a3c0e] = true; // EIP-5192 soulbound
        ds.supportedInterfaces[0x1f931c1c] = true; // IRouterAdmin
        ds.supportedInterfaces[0x48e2b093] = true; // IRouterIntrospection
    }

    function setLineageRegistries(address _nameRegistry, address _versionRegistry) external {
        LibAccessControl.checkRole(LibAccessControl.ADMIN_ROLE);
        LibLifecycleStorage.Layout storage l = LibLifecycleStorage.layout();
        l.nameRegistry = SMARTNameRegistry(_nameRegistry);
        l.versionRegistry = SMARTVersionRegistry(_versionRegistry);
    }

    function setIdentityRegistry(address _registry) external {
        LibAccessControl.checkRole(LibAccessControl.ADMIN_ROLE);
        LibLifecycleStorage.Layout storage l = LibLifecycleStorage.layout();
        address previous = address(l.identityRegistry);
        l.identityRegistry = SMARTIdentityRegistry(_registry);
        emit LifecycleEvents.IdentityRegistryUpdated(previous, _registry, block.timestamp);
    }

    function setStrictMode(uint8 transitionType, bool required) external {
        LibAccessControl.checkRole(LibAccessControl.ADMIN_ROLE);
        LibLifecycleStorage.Layout storage l = LibLifecycleStorage.layout();
        l.requireIdentityForTransition[transitionType] = required;
        emit LifecycleEvents.StrictModeChanged(transitionType, required, block.timestamp);
    }

    function setChallengeWindowSeconds(uint64 secs) external {
        LibAccessControl.checkRole(LibAccessControl.ADMIN_ROLE);
        LibLifecycleStorage.Layout storage l = LibLifecycleStorage.layout();
        emit LifecycleEvents.ChallengeWindowChanged(l.challengeWindowSeconds, secs, block.timestamp);
        l.challengeWindowSeconds = secs;
    }

    function setSBTContract(address _sbtContract) external {
        LibAccessControl.checkRole(LibAccessControl.ADMIN_ROLE);
        LibLifecycleStorage.Layout storage l = LibLifecycleStorage.layout();
        address previous = address(l.sbtContract);
        l.sbtContract = ISMARTModelCardSBT(_sbtContract);
        emit LifecycleEvents.SBTContractUpdated(previous, _sbtContract, block.timestamp);
    }

    function adminEmergencyPublish(uint256 tokenId, string memory justification, address actor) external {
        LibAccessControl.checkRole(LibAccessControl.ADMIN_ROLE);
        require(actor != address(0), "Actor required");
        require(bytes(justification).length >= 10, "Justification required (min 10 chars)");

        LibLifecycleStorage.Layout storage l = LibLifecycleStorage.layout();
        LibLifecycleStorage.ModelCard storage card = l.modelCards[tokenId];
        require(card.isActive, "Model card not active");
        require(card.status == LibLifecycleStorage.Status.Validated, "Not validated");

        LibLifecycleCore.updateStatus(tokenId, LibLifecycleStorage.Status.Published, actor);
        LibLifecycleCore.recordAction(
            tokenId, actor,
            LibLifecycleStorage.Status.Validated, LibLifecycleStorage.Status.Published,
            LibLifecycleStorage.TransitionType.AdminPublish, card.contentHash
        );
        LibLifecycleCore.mintProvenanceSBT(tokenId, card);

        emit LifecycleEvents.AdminOverride(tokenId, actor, "EMERGENCY_PUBLISH", justification, block.timestamp);
        emit LifecycleEvents.ModelCardPublished(tokenId, actor, block.timestamp);
    }

    function adminEmergencyDeprecate(
        uint256 tokenId,
        string memory reason,
        string memory justification,
        address actor
    ) external {
        LibAccessControl.checkRole(LibAccessControl.ADMIN_ROLE);
        require(actor != address(0), "Actor required");
        require(bytes(justification).length >= 10, "Justification required (min 10 chars)");

        LibLifecycleStorage.Layout storage l = LibLifecycleStorage.layout();
        LibLifecycleStorage.ModelCard storage card = l.modelCards[tokenId];
        require(card.isActive, "Model card not active");
        require(card.status == LibLifecycleStorage.Status.Published, "Not published");

        LibLifecycleCore.updateStatus(tokenId, LibLifecycleStorage.Status.Deprecated, actor);
        card.isActive = false;
        card.revisionNotes = reason;
        LibLifecycleCore.recordAction(
            tokenId, actor,
            LibLifecycleStorage.Status.Published, LibLifecycleStorage.Status.Deprecated,
            LibLifecycleStorage.TransitionType.AdminDeprecate, card.contentHash
        );

        emit LifecycleEvents.AdminOverride(tokenId, actor, "EMERGENCY_DEPRECATE", justification, block.timestamp);
        emit LifecycleEvents.ModelCardDeprecated(tokenId, actor, reason, block.timestamp);
    }

    function hasRole(bytes32 role, address account) external view returns (bool) {
        return LibAccessControl.hasRole(role, account);
    }

    function getRoleAdmin(bytes32 role) external view returns (bytes32) {
        return LibAccessControl.getRoleAdmin(role);
    }

    function grantRole(bytes32 role, address account) external {
        LibAccessControl.checkRole(LibAccessControl.getRoleAdmin(role));
        LibAccessControl._grantRole(role, account);
    }

    function revokeRole(bytes32 role, address account) external {
        LibAccessControl.checkRole(LibAccessControl.getRoleAdmin(role));
        LibAccessControl._revokeRole(role, account);
    }

    function renounceRole(bytes32 role, address account) external {
        require(account == msg.sender, "AccessControl: can only renounce roles for self");
        LibAccessControl._revokeRole(role, account);
    }

    function DEFAULT_ADMIN_ROLE() external pure returns (bytes32) {
        return LibAccessControl.DEFAULT_ADMIN_ROLE;
    }
    function DEVELOPER_ROLE() external pure returns (bytes32) {
        return LibAccessControl.DEVELOPER_ROLE;
    }
    function AUTHENTICATOR_ROLE() external pure returns (bytes32) {
        return LibAccessControl.AUTHENTICATOR_ROLE;
    }
    function PUBLISHER_ROLE() external pure returns (bytes32) {
        return LibAccessControl.PUBLISHER_ROLE;
    }
    function ADMIN_ROLE() external pure returns (bytes32) {
        return LibAccessControl.ADMIN_ROLE;
    }
    function IDENTITY_ARBITER_ROLE() external pure returns (bytes32) {
        return LibAccessControl.IDENTITY_ARBITER_ROLE;
    }
}
