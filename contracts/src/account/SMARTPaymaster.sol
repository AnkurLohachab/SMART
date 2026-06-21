// SPDX-License-Identifier: MIT
pragma solidity ^0.8.27;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "./SMARTAccount.sol";
import "../utils/SMARTRoles.sol";

interface IEntryPointPaymaster {
    struct UserOperation {
        address sender;
        uint256 nonce;
        bytes initCode;
        bytes callData;
        uint256 callGasLimit;
        uint256 verificationGasLimit;
        uint256 preVerificationGas;
        uint256 maxFeePerGas;
        uint256 maxPriorityFeePerGas;
        bytes paymasterAndData;
        bytes signature;
    }

    function depositTo(address account) external payable;
    function withdrawTo(address payable withdrawAddress, uint256 withdrawAmount) external;
    function balanceOf(address account) external view returns (uint256);
    function getDepositInfo(address account) external view returns (
        uint112 deposit,
        bool staked,
        uint112 stake,
        uint32 unstakeDelaySec,
        uint48 withdrawTime
    );
}

interface IPaymaster {
    function validatePaymasterUserOp(
        IEntryPointPaymaster.UserOperation calldata userOp,
        bytes32 userOpHash,
        uint256 maxCost
    ) external returns (bytes memory context, uint256 validationData);

    function postOp(
        PostOpMode mode,
        bytes calldata context,
        uint256 actualGasCost
    ) external;

    enum PostOpMode {
        opSucceeded,
        opReverted,
        postOpReverted
    }
}

contract SMARTPaymaster is IPaymaster, Ownable, ReentrancyGuard {
    using SafeERC20 for IERC20;

    // ============== Constants ==============

    uint256 internal constant SIG_VALIDATION_SUCCESS = 0;
    uint256 internal constant SIG_VALIDATION_FAILED = 1;

    // ============== State Variables ==============

    IEntryPointPaymaster public immutable entryPoint;

    IERC20 public paymentToken;

    uint256 public tokenPriceInWei;

    bool public tokenPaymentsEnabled;

    bool public sponsorshipEnabled;

    // ============== Sponsorship Configuration ==============

    uint256 public dailyGasLimit;

    uint256 public monthlyGasLimit;

    uint256 public maxOperationCost;

    // ============== Tracking ==============

    mapping(address => mapping(uint256 => uint256)) public dailyGasUsed;

    mapping(address => mapping(uint256 => uint256)) public monthlyGasUsed;

    mapping(address => bool) public whitelistedAccounts;

    mapping(address => bool) public blacklistedAccounts;

    mapping(SMARTRole => uint256) public roleMultipliers;

    // ============== Events ==============

    event GasSponsored(
        address indexed account,
        uint256 gasUsed,
        uint256 timestamp
    );

    event TokenPayment(
        address indexed account,
        uint256 tokenAmount,
        uint256 gasCost
    );

    event SponsorshipConfigUpdated(
        uint256 dailyLimit,
        uint256 monthlyLimit,
        uint256 maxOpCost
    );

    event AccountWhitelisted(address indexed account, bool status);
    event AccountBlacklisted(address indexed account, bool status);
    event TokenPaymentsToggled(bool enabled);
    event SponsorshipToggled(bool enabled);
    event Deposited(address indexed from, uint256 amount);
    event Withdrawn(address indexed to, uint256 amount);

    // ============== Constructor ==============

    constructor(address _entryPoint) {
        require(_entryPoint != address(0), "SMARTPaymaster: invalid EntryPoint");
        entryPoint = IEntryPointPaymaster(_entryPoint);

        // Default configuration
        dailyGasLimit = 0.1 ether;      // 0.1 ETH worth of gas per day
        monthlyGasLimit = 1 ether;       // 1 ETH worth of gas per month
        maxOperationCost = 0.01 ether;   // 0.01 ETH max per operation
        sponsorshipEnabled = true;

        // Default role multipliers
        roleMultipliers[SMARTRole.Reader] = 50;        // 0.5x
        roleMultipliers[SMARTRole.AIDeveloper] = 200;  // 2x
        roleMultipliers[SMARTRole.Authenticator] = 150; // 1.5x
        roleMultipliers[SMARTRole.Publisher] = 150;     // 1.5x
        roleMultipliers[SMARTRole.Admin] = 300;         // 3x
    }

    // ============== EIP-4337 Paymaster Interface ==============

    function validatePaymasterUserOp(
        IEntryPointPaymaster.UserOperation calldata userOp,
        bytes32 userOpHash,
        uint256 maxCost
    ) external override returns (bytes memory context, uint256 validationData) {
        require(msg.sender == address(entryPoint), "SMARTPaymaster: not EntryPoint");

        // Check global sponsorship
        if (!sponsorshipEnabled) {
            return ("", SIG_VALIDATION_FAILED);
        }

        address sender = userOp.sender;

        // Check blacklist
        if (blacklistedAccounts[sender]) {
            return ("", SIG_VALIDATION_FAILED);
        }

        // Check cost limits
        if (maxCost > maxOperationCost && !whitelistedAccounts[sender]) {
            return ("", SIG_VALIDATION_FAILED);
        }

        // Check daily/monthly limits (skip for whitelisted)
        if (!whitelistedAccounts[sender]) {
            uint256 multiplier = _getMultiplier(sender);
            uint256 adjustedDailyLimit = (dailyGasLimit * multiplier) / 100;
            uint256 adjustedMonthlyLimit = (monthlyGasLimit * multiplier) / 100;

            uint256 currentDay = block.timestamp / 1 days;
            uint256 currentMonth = block.timestamp / 30 days;

            if (dailyGasUsed[sender][currentDay] + maxCost > adjustedDailyLimit) {
                return ("", SIG_VALIDATION_FAILED);
            }

            if (monthlyGasUsed[sender][currentMonth] + maxCost > adjustedMonthlyLimit) {
                return ("", SIG_VALIDATION_FAILED);
            }
        }

        // Encode context for postOp
        context = abi.encode(sender, maxCost, block.timestamp);

        // Suppress unused parameter warning
        (userOpHash);

        return (context, SIG_VALIDATION_SUCCESS);
    }

    function postOp(
        PostOpMode mode,
        bytes calldata context,
        uint256 actualGasCost
    ) external override {
        require(msg.sender == address(entryPoint), "SMARTPaymaster: not EntryPoint");

        (address sender, , ) = abi.decode(context, (address, uint256, uint256));

        // Update usage tracking
        uint256 currentDay = block.timestamp / 1 days;
        uint256 currentMonth = block.timestamp / 30 days;

        dailyGasUsed[sender][currentDay] += actualGasCost;
        monthlyGasUsed[sender][currentMonth] += actualGasCost;

        emit GasSponsored(sender, actualGasCost, block.timestamp);

        // Suppress unused parameter warning
        (mode);
    }

    // ============== Internal Functions ==============

    function _getMultiplier(address account) internal view returns (uint256) {
        try SMARTAccount(payable(account)).accountRole() returns (SMARTRole role) {
            uint256 mult = roleMultipliers[role];
            return mult > 0 ? mult : 100;
        } catch {
            return 100; // Default 1x
        }
    }

    // ============== Admin Functions ==============

    function deposit() external payable onlyOwner {
        entryPoint.depositTo{value: msg.value}(address(this));
        emit Deposited(msg.sender, msg.value);
    }

    function withdraw(address payable to, uint256 amount) external onlyOwner nonReentrant {
        entryPoint.withdrawTo(to, amount);
        emit Withdrawn(to, amount);
    }

    function setSponsorshipConfig(
        uint256 _dailyLimit,
        uint256 _monthlyLimit,
        uint256 _maxOpCost
    ) external onlyOwner {
        dailyGasLimit = _dailyLimit;
        monthlyGasLimit = _monthlyLimit;
        maxOperationCost = _maxOpCost;
        emit SponsorshipConfigUpdated(_dailyLimit, _monthlyLimit, _maxOpCost);
    }

    function setRoleMultiplier(SMARTRole role, uint256 multiplier) external onlyOwner {
        roleMultipliers[role] = multiplier;
    }

    function setWhitelisted(address account, bool status) external onlyOwner {
        whitelistedAccounts[account] = status;
        emit AccountWhitelisted(account, status);
    }

    function setBlacklisted(address account, bool status) external onlyOwner {
        blacklistedAccounts[account] = status;
        emit AccountBlacklisted(account, status);
    }

    function toggleSponsorship(bool enabled) external onlyOwner {
        sponsorshipEnabled = enabled;
        emit SponsorshipToggled(enabled);
    }

    function configureTokenPayments(
        address _token,
        uint256 _priceInWei,
        bool _enabled
    ) external onlyOwner {
        paymentToken = IERC20(_token);
        tokenPriceInWei = _priceInWei;
        tokenPaymentsEnabled = _enabled;
        emit TokenPaymentsToggled(_enabled);
    }

    // ============== View Functions ==============

    function getRemainingDailyQuota(address account) external view returns (uint256) {
        uint256 multiplier = _getMultiplier(account);
        uint256 limit = whitelistedAccounts[account]
            ? type(uint256).max
            : (dailyGasLimit * multiplier) / 100;

        uint256 currentDay = block.timestamp / 1 days;
        uint256 used = dailyGasUsed[account][currentDay];

        return used >= limit ? 0 : limit - used;
    }

    function getRemainingMonthlyQuota(address account) external view returns (uint256) {
        uint256 multiplier = _getMultiplier(account);
        uint256 limit = whitelistedAccounts[account]
            ? type(uint256).max
            : (monthlyGasLimit * multiplier) / 100;

        uint256 currentMonth = block.timestamp / 30 days;
        uint256 used = monthlyGasUsed[account][currentMonth];

        return used >= limit ? 0 : limit - used;
    }

    function getDeposit() external view returns (uint256) {
        return entryPoint.balanceOf(address(this));
    }

    // ============== Receive ETH ==============

    receive() external payable {
        if (msg.value > 0) {
            entryPoint.depositTo{value: msg.value}(address(this));
            emit Deposited(msg.sender, msg.value);
        }
    }
}
