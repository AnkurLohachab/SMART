// SPDX-License-Identifier: MIT
pragma solidity ^0.8.27;

import "@openzeppelin/contracts/access/Ownable.sol";
import "../utils/SMARTRoles.sol";

contract SMARTUsernameRegistry is Ownable {
    // ============== State Variables ==============

    mapping(string => mapping(SMARTRole => address)) private usernameToAccount;

    mapping(address => string) public accountToUsername;

    uint256 public totalRegistrations;

    // ============== Events ==============

    event UsernameRegistered(
        string indexed username,
        SMARTRole indexed role,
        address indexed account,
        uint256 timestamp
    );

    event UsernameDeregistered(
        string indexed username,
        SMARTRole indexed role,
        uint256 timestamp
    );

    // ============== Constructor ==============

    constructor() {
        // Deployer is owner by default in OZ v4
    }

    // ============== Registration Functions ==============

    function registerUsername(
        string calldata username,
        SMARTRole role,
        address account
    ) external onlyOwner {
        require(bytes(username).length > 0, "SMARTUsernameRegistry: empty username");
        require(account != address(0), "SMARTUsernameRegistry: zero address");
        require(
            usernameToAccount[username][role] == address(0),
            "SMARTUsernameRegistry: username+role taken"
        );

        usernameToAccount[username][role] = account;
        accountToUsername[account] = username;
        totalRegistrations++;

        emit UsernameRegistered(username, role, account, block.timestamp);
    }

    function deregisterUsername(
        string calldata username,
        SMARTRole role
    ) external onlyOwner {
        address account = usernameToAccount[username][role];
        require(account != address(0), "SMARTUsernameRegistry: not registered");

        delete usernameToAccount[username][role];
        delete accountToUsername[account];

        emit UsernameDeregistered(username, role, block.timestamp);
    }

    // ============== View Functions ==============

    function isUsernameAvailable(
        string calldata username,
        SMARTRole role
    ) external view returns (bool) {
        return usernameToAccount[username][role] == address(0);
    }

    function getAccountByUsername(
        string calldata username,
        SMARTRole role
    ) external view returns (address) {
        return usernameToAccount[username][role];
    }

    function getUsernameByAccount(
        address account
    ) external view returns (string memory) {
        return accountToUsername[account];
    }

    function isAccountRegistered(address account) external view returns (bool) {
        return bytes(accountToUsername[account]).length > 0;
    }
}
