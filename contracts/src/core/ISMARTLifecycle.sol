// SPDX-License-Identifier: MIT
pragma solidity ^0.8.27;

import "./SMARTVersionRegistry.sol";

interface ISMARTLifecycle {
    function createModelCard(address creator, string calldata metadataURI, bytes32 contentHash)
        external returns (uint256);

    function createModelCardWithLineage(
        address creator,
        string calldata name,
        string calldata metadataURI,
        bytes32 contentHash,
        uint256 supersedes,
        SMARTVersionRegistry.Relation relation,
        bool withinEnvelope
    ) external returns (uint256 tokenId, bytes memory aliasOut);

    function pinLineEnvelope(string calldata name, bytes32 envelopeHash, address controller) external;
    function updateLineEnvelope(string calldata name, bytes32 newHash, address controller) external;

    function submitForEvaluation(uint256 tokenId, address actor) external;
    function validateModelCard(uint256 tokenId, address actor) external;
    function rejectModelCard(uint256 tokenId, string calldata reason, address actor) external;
    function requestRevision(uint256 tokenId, string calldata feedback, address actor) external;
    function reviseModelCard(
        uint256 tokenId,
        string calldata newMetadataURI,
        bytes32 newContentHash,
        string calldata revisionNotes,
        address actor
    ) external;
    function publishModelCard(uint256 tokenId, address actor) external;
    function deprecateModelCard(uint256 tokenId, string calldata reason, address actor) external;

    function adminEmergencyPublish(uint256 tokenId, string calldata justification, address actor) external;
    function adminEmergencyDeprecate(
        uint256 tokenId,
        string calldata reason,
        string calldata justification,
        address actor
    ) external;
}
