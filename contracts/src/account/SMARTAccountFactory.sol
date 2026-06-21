// SPDX-License-Identifier: MIT
pragma solidity ^0.8.27;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/Create2.sol";
import "./SMARTAccount.sol";
import "./SMARTUsernameRegistry.sol";
import "../utils/SMARTRoles.sol";

contract SMARTAccountFactory is Ownable {
    // ============== State Variables ==============

    SMARTUsernameRegistry public usernameRegistry;

    address public relayer;

    mapping(string => mapping(SMARTRole => address)) public accountOfUsername;

    mapping(address => address) public ownerOfAccount;

    mapping(address => address[]) public accountsOfOwner;

    uint256 public totalAccounts;

    // ============== Events ==============

    event AccountCreated(
        string indexed username,
        SMARTRole indexed role,
        address indexed account,
        address owner,
        uint256 timestamp
    );

    event RelayerUpdated(address indexed previousRelayer, address indexed newRelayer);

    // ============== Constructor ==============

    constructor(address _usernameRegistry) {
        require(_usernameRegistry != address(0), "SMARTAccountFactory: invalid registry");
        usernameRegistry = SMARTUsernameRegistry(_usernameRegistry);
        relayer = msg.sender;
    }

    // ============== Account Creation ==============

    function createAccount(
        address owner,
        string memory username,
        SMARTRole role
    ) public returns (address accountAddress) {
        require(
            msg.sender == owner || msg.sender == relayer || msg.sender == Ownable.owner(),
            "SMARTAccountFactory: unauthorized"
        );
        require(owner != address(0), "SMARTAccountFactory: invalid owner");
        require(bytes(username).length > 0, "SMARTAccountFactory: empty username");
        require(
            accountOfUsername[username][role] == address(0),
            "SMARTAccountFactory: account exists for username+role"
        );

        // Create account using CREATE2 for deterministic address
        bytes32 salt = keccak256(abi.encodePacked(username, uint8(role)));
        SMARTAccount account = new SMARTAccount{salt: salt}(owner, username, role);
        accountAddress = address(account);

        // Store mappings
        accountOfUsername[username][role] = accountAddress;
        ownerOfAccount[accountAddress] = owner;
        accountsOfOwner[owner].push(accountAddress);
        totalAccounts++;

        // Register username with role in registry - MUST succeed (hard check)
        require(
            usernameRegistry.isUsernameAvailable(username, role),
            "SMARTAccountFactory: username+role already taken"
        );
        usernameRegistry.registerUsername(username, role, accountAddress);

        emit AccountCreated(username, role, accountAddress, owner, block.timestamp);

        return accountAddress;
    }

    function createAllRoleAccounts(
        address owner,
        string memory username
    ) external returns (address[] memory accounts) {
        accounts = new address[](5);

        accounts[0] = createAccount(owner, username, SMARTRole.Reader);
        accounts[1] = createAccount(owner, username, SMARTRole.AIDeveloper);
        accounts[2] = createAccount(owner, username, SMARTRole.Authenticator);
        accounts[3] = createAccount(owner, username, SMARTRole.Publisher);
        accounts[4] = createAccount(owner, username, SMARTRole.Admin);

        return accounts;
    }

    // ============== View Functions ==============

    function getAccount(
        string memory username,
        SMARTRole role
    ) external view returns (address) {
        return accountOfUsername[username][role];
    }

    function getAccountsOfOwner(
        address owner
    ) external view returns (address[] memory) {
        return accountsOfOwner[owner];
    }

    function accountExists(
        string memory username,
        SMARTRole role
    ) external view returns (bool) {
        return accountOfUsername[username][role] != address(0);
    }

    function computeAddress(
        address owner,
        string memory username,
        SMARTRole role
    ) external view returns (address) {
        bytes32 salt = keccak256(abi.encodePacked(username, uint8(role)));
        bytes32 hash = keccak256(
            abi.encodePacked(
                bytes1(0xff),
                address(this),
                salt,
                keccak256(
                    abi.encodePacked(
                        type(SMARTAccount).creationCode,
                        abi.encode(owner, username, role)
                    )
                )
            )
        );
        return address(uint160(uint256(hash)));
    }

    // ============== Admin Functions ==============

    function setRelayer(address newRelayer) external onlyOwner {
        address previousRelayer = relayer;
        relayer = newRelayer;
        emit RelayerUpdated(previousRelayer, newRelayer);
    }

    function setUsernameRegistry(address newRegistry) external onlyOwner {
        require(newRegistry != address(0), "SMARTAccountFactory: invalid registry");
        usernameRegistry = SMARTUsernameRegistry(newRegistry);
    }
}
