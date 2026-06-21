// SPDX-License-Identifier: MIT
pragma solidity ^0.8.27;

import "../libraries/LibLifecycleStorage.sol";
import "../libraries/LifecycleEvents.sol";

contract LifecycleNFT {

    error AddressZero();
    error NonexistentToken();
    error Soulbound();

    function balanceOf(address owner) external view returns (uint256) {
        if (owner == address(0)) revert AddressZero();
        return LibLifecycleStorage.layout().erc721Balances[owner];
    }

    function ownerOf(uint256 tokenId) external view returns (address) {
        address owner = LibLifecycleStorage.layout().erc721Owners[tokenId];
        if (owner == address(0)) revert NonexistentToken();
        return owner;
    }

    function name() external view returns (string memory) {
        return LibLifecycleStorage.layout().erc721Name;
    }

    function symbol() external view returns (string memory) {
        return LibLifecycleStorage.layout().erc721Symbol;
    }

    function tokenURI(uint256 tokenId) external view returns (string memory) {
        LibLifecycleStorage.Layout storage l = LibLifecycleStorage.layout();
        if (l.erc721Owners[tokenId] == address(0)) revert NonexistentToken();
        return l.modelCards[tokenId].metadataURI;
    }

    function getApproved(uint256 tokenId) external view returns (address) {
        // Soulbound tokens are never approved.
        if (LibLifecycleStorage.layout().erc721Owners[tokenId] == address(0)) {
            revert NonexistentToken();
        }
        return address(0);
    }

    function isApprovedForAll(address /*owner*/, address /*operator*/) external pure returns (bool) {
        return false;
    }

    function transferFrom(address, address, uint256) external pure {
        revert("SMARTLifecycle: Soulbound tokens cannot be transferred");
    }

    function safeTransferFrom(address, address, uint256) external pure {
        revert("SMARTLifecycle: Soulbound tokens cannot be transferred");
    }

    function safeTransferFrom(address, address, uint256, bytes calldata) external pure {
        revert("SMARTLifecycle: Soulbound tokens cannot be transferred");
    }

    function approve(address, uint256) external pure {
        revert("SMARTLifecycle: Soulbound tokens cannot be transferred");
    }

    function setApprovalForAll(address, bool) external pure {
        revert("SMARTLifecycle: Soulbound tokens cannot be transferred");
    }

    function locked(uint256 tokenId) external view returns (bool) {
        if (LibLifecycleStorage.layout().erc721Owners[tokenId] == address(0)) {
            revert NonexistentToken();
        }
        return true;
    }

    // ERC-165 supportsInterface owned by RouterIntrospection (single source).
    // Initial supportedInterfaces flags set in LifecycleAdmin.initialize().

    function getActionsForToken(uint256 tokenId) external view returns (uint256[] memory) {
        return LibLifecycleStorage.layout().actionsForToken[tokenId];
    }

    function getAction(uint256 actionId)
        external
        view
        returns (LibLifecycleStorage.ActionRecord memory)
    {
        return LibLifecycleStorage.layout().actionById[actionId];
    }

    function getGovernance(uint256 tokenId)
        external
        view
        returns (uint32 invalidCount, uint8 highestRepudiated)
    {
        LibLifecycleStorage.Layout storage l = LibLifecycleStorage.layout();
        return (l.invalidGovernanceActionCount[tokenId], l.highestRepudiatedToState[tokenId]);
    }

    function getStatusHistory(uint256 tokenId)
        external
        view
        returns (LibLifecycleStorage.Status[] memory)
    {
        if (LibLifecycleStorage.layout().erc721Owners[tokenId] == address(0)) revert NonexistentToken();
        return LibLifecycleStorage.layout().statusHistory[tokenId];
    }

    function getRevisionHistory(uint256 tokenId)
        external
        view
        returns (LibLifecycleStorage.RevisionRecord[] memory)
    {
        if (LibLifecycleStorage.layout().erc721Owners[tokenId] == address(0)) revert NonexistentToken();
        return LibLifecycleStorage.layout().revisionHistory[tokenId];
    }

    function getRevision(uint256 tokenId, uint256 revisionIndex)
        external
        view
        returns (LibLifecycleStorage.RevisionRecord memory)
    {
        LibLifecycleStorage.Layout storage l = LibLifecycleStorage.layout();
        if (l.erc721Owners[tokenId] == address(0)) revert NonexistentToken();
        require(revisionIndex < l.revisionHistory[tokenId].length, "Invalid revision index");
        return l.revisionHistory[tokenId][revisionIndex];
    }

    function getVersion(uint256 tokenId) external view returns (uint256) {
        LibLifecycleStorage.Layout storage l = LibLifecycleStorage.layout();
        if (l.erc721Owners[tokenId] == address(0)) revert NonexistentToken();
        return l.modelCards[tokenId].version;
    }

    function getRemainingRevisions(uint256 tokenId) external view returns (uint256) {
        LibLifecycleStorage.Layout storage l = LibLifecycleStorage.layout();
        if (l.erc721Owners[tokenId] == address(0)) revert NonexistentToken();
        return 10 - l.modelCards[tokenId].revisionCount; // MAX_REVISIONS = 10
    }

    function getTotalModelCards() external view returns (uint256) {
        return LibLifecycleStorage.layout().tokenIdCounter;
    }

    function getSBTTokenId(uint256 tokenId) external view returns (uint256) {
        return LibLifecycleStorage.layout().lifecycleToSBT[tokenId];
    }

    function isSBTEnabled() external view returns (bool) {
        return address(LibLifecycleStorage.layout().sbtContract) != address(0);
    }

    function nextActionId() external view returns (uint256) {
        return LibLifecycleStorage.layout().nextActionId;
    }

    function challengeWindowSeconds() external view returns (uint64) {
        return LibLifecycleStorage.layout().challengeWindowSeconds;
    }

    function identityRegistry() external view returns (address) {
        return address(LibLifecycleStorage.layout().identityRegistry);
    }

    function nameRegistry() external view returns (address) {
        return address(LibLifecycleStorage.layout().nameRegistry);
    }

    function versionRegistry() external view returns (address) {
        return address(LibLifecycleStorage.layout().versionRegistry);
    }

    function sbtContract() external view returns (address) {
        return address(LibLifecycleStorage.layout().sbtContract);
    }

    function modelCards(uint256 tokenId)
        external
        view
        returns (LibLifecycleStorage.ModelCard memory)
    {
        return LibLifecycleStorage.layout().modelCards[tokenId];
    }

    function MAX_REVISIONS() external pure returns (uint256) { return 10; }
    function SCHEMA_VERSION() external pure returns (string memory) { return "1.0.0"; }
}
