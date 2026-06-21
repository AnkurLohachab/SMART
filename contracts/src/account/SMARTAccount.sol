// SPDX-License-Identifier: MIT
pragma solidity ^0.8.27;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import "../utils/SMARTRoles.sol";

contract SMARTAccount is Ownable {
    using ECDSA for bytes32;

    SMARTRole public accountRole;

    string public username;

    bool public isActive;

    uint256 public createdAt;

    // ============== Events ==============

    event RoleUpdated(SMARTRole previousRole, SMARTRole newRole);
    event AccountDeactivated(address indexed deactivatedBy);
    event AccountReactivated(address indexed reactivatedBy);
    event TransactionExecuted(address indexed target, uint256 value, bool success);

    // ============== Constructor ==============

    constructor(address _owner, string memory _username, SMARTRole _role) {
        require(_owner != address(0), "SMARTAccount: invalid owner");
        require(bytes(_username).length > 0, "SMARTAccount: empty username");

        _transferOwnership(_owner);
        username = _username;
        accountRole = _role;
        isActive = true;
        createdAt = block.timestamp;
    }

    // ============== Role Management ==============

    function updateRole(SMARTRole newRole) external onlyOwner {
        SMARTRole previousRole = accountRole;
        accountRole = newRole;
        emit RoleUpdated(previousRole, newRole);
    }

    // ============== Account Lifecycle ==============

    function deactivate() external onlyOwner {
        require(isActive, "SMARTAccount: already deactivated");
        isActive = false;
        emit AccountDeactivated(msg.sender);
    }

    function reactivate() external onlyOwner {
        require(!isActive, "SMARTAccount: already active");
        isActive = true;
        emit AccountReactivated(msg.sender);
    }

    // ============== Role Checking ==============

    function hasRole(SMARTRole role) external view returns (bool) {
        return isActive && accountRole == role;
    }

    function hasMinimumRole(SMARTRole minimumRole) external view returns (bool) {
        return isActive && uint8(accountRole) >= uint8(minimumRole);
    }

    // ============== Transaction Execution ==============

    function execute(
        address target,
        uint256 value,
        bytes calldata data
    ) external payable onlyOwner returns (bytes memory result) {
        require(isActive, "SMARTAccount: account not active");
        require(target != address(0), "SMARTAccount: invalid target");

        (bool success, bytes memory returnData) = target.call{value: value}(data);

        emit TransactionExecuted(target, value, success);

        if (!success) {
            // Bubble up revert reason
            if (returnData.length > 0) {
                assembly {
                    revert(add(returnData, 32), mload(returnData))
                }
            }
            revert("SMARTAccount: execution failed");
        }

        return returnData;
    }

    function executeBatch(
        address[] calldata targets,
        uint256[] calldata values,
        bytes[] calldata datas
    ) external payable onlyOwner {
        require(isActive, "SMARTAccount: account not active");
        require(
            targets.length == values.length && values.length == datas.length,
            "SMARTAccount: array length mismatch"
        );

        for (uint256 i = 0; i < targets.length; i++) {
            require(targets[i] != address(0), "SMARTAccount: invalid target");
            (bool success, bytes memory returnData) = targets[i].call{value: values[i]}(datas[i]);

            emit TransactionExecuted(targets[i], values[i], success);

            if (!success) {
                if (returnData.length > 0) {
                    assembly {
                        revert(add(returnData, 32), mload(returnData))
                    }
                }
                revert("SMARTAccount: batch execution failed");
            }
        }
    }

    // ============== View Functions ==============

    function getAccountInfo() external view returns (
        address _owner,
        string memory _username,
        SMARTRole _role,
        bool _isActive,
        uint256 _createdAt
    ) {
        return (owner(), username, accountRole, isActive, createdAt);
    }

    // ============== Receive ETH ==============

    receive() external payable {}
    fallback() external payable {}
}
