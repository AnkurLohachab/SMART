// SPDX-License-Identifier: MIT
pragma solidity ^0.8.27;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import "../core/ISMARTLifecycle.sol";
import "./SMARTAccountFactory.sol";
import "../utils/SMARTRoles.sol";

contract SMARTRelayer is Ownable {
    using ECDSA for bytes32;

    ISMARTLifecycle public lifecycleContract;

    SMARTAccountFactory public accountFactory;

    mapping(address => uint256) public nonces;

    event RelayedCreateModelCard(uint256 indexed tokenId, address indexed creator);
    event RelayedSubmitForEvaluation(uint256 indexed tokenId, address indexed initiator);
    event RelayedValidateModelCard(uint256 indexed tokenId, address indexed validator);
    event RelayedRejectModelCard(uint256 indexed tokenId, address indexed rejector);
    event RelayedRequestRevision(uint256 indexed tokenId, address indexed requester);
    event RelayedReviseModelCard(uint256 indexed tokenId, address indexed revisor);
    event RelayedPublishModelCard(uint256 indexed tokenId, address indexed publisher);
    event RelayedDeprecateModelCard(uint256 indexed tokenId, address indexed deprecator);
    event RelayedAdminEmergencyPublish(uint256 indexed tokenId, address indexed admin);
    event RelayedAdminEmergencyDeprecate(uint256 indexed tokenId, address indexed admin);

    constructor(address _lifecycleContract, address _accountFactory) {
        require(_lifecycleContract != address(0), "SMARTRelayer: invalid lifecycle");
        require(_accountFactory != address(0), "SMARTRelayer: invalid factory");

        lifecycleContract = ISMARTLifecycle(_lifecycleContract);
        accountFactory = SMARTAccountFactory(_accountFactory);
    }

    function _verifySignature(
        address signer,
        bytes32 messageHash,
        bytes memory signature
    ) internal pure returns (bool) {
        bytes32 ethSignedMessageHash = messageHash.toEthSignedMessageHash();
        address recovered = ethSignedMessageHash.recover(signature);
        return recovered == signer;
    }

    function relayCreateModelCard(
        address creator,
        string memory metadataURI,
        bytes32 contentHash,
        bytes memory signature
    ) external returns (uint256) {
        bytes32 messageHash = keccak256(
            abi.encodePacked(creator, metadataURI, contentHash, nonces[creator])
        );
        require(
            _verifySignature(creator, messageHash, signature),
            "SMARTRelayer: invalid signature"
        );

        nonces[creator]++;

        uint256 tokenId = lifecycleContract.createModelCard(creator, metadataURI, contentHash);

        emit RelayedCreateModelCard(tokenId, creator);
        return tokenId;
    }

    function relayPinLineEnvelope(
        string memory name,
        bytes32 envelopeHash,
        address controller,
        bytes memory signature
    ) external {
        bytes32 messageHash = keccak256(
            abi.encodePacked(name, envelopeHash, controller, nonces[controller])
        );
        require(
            _verifySignature(controller, messageHash, signature),
            "SMARTRelayer: invalid signature"
        );
        nonces[controller]++;
        lifecycleContract.pinLineEnvelope(name, envelopeHash, controller);
    }

    function relayUpdateLineEnvelope(
        string memory name,
        bytes32 newHash,
        address controller,
        bytes memory signature
    ) external {
        bytes32 messageHash = keccak256(
            abi.encodePacked("update", name, newHash, controller, nonces[controller])
        );
        require(
            _verifySignature(controller, messageHash, signature),
            "SMARTRelayer: invalid signature"
        );
        nonces[controller]++;
        lifecycleContract.updateLineEnvelope(name, newHash, controller);
    }

    function relayCreateModelCardWithLineage(
        address creator,
        string memory name,
        string memory metadataURI,
        bytes32 contentHash,
        uint256 supersedes,
        uint8 relation,
        bool withinEnvelope,
        bytes memory signature
    ) external returns (uint256 tokenId, bytes memory aliasOut) {
        bytes32 messageHash = keccak256(
            abi.encodePacked(
                creator, name, metadataURI, contentHash,
                supersedes, relation, withinEnvelope, nonces[creator]
            )
        );
        require(
            _verifySignature(creator, messageHash, signature),
            "SMARTRelayer: invalid signature"
        );
        nonces[creator]++;

        (tokenId, aliasOut) = lifecycleContract.createModelCardWithLineage(
            creator,
            name,
            metadataURI,
            contentHash,
            supersedes,
            SMARTVersionRegistry.Relation(relation),
            withinEnvelope
        );

        emit RelayedCreateModelCard(tokenId, creator);
    }

    function relaySubmitForEvaluation(
        uint256 tokenId,
        address initiator,
        bytes memory signature
    ) external {
        bytes32 messageHash = keccak256(
            abi.encodePacked(tokenId, initiator, nonces[initiator])
        );
        require(
            _verifySignature(initiator, messageHash, signature),
            "SMARTRelayer: invalid signature"
        );

        nonces[initiator]++;

        lifecycleContract.submitForEvaluation(tokenId, initiator);

        emit RelayedSubmitForEvaluation(tokenId, initiator);
    }

    function relayValidateModelCard(
        uint256 tokenId,
        address validator,
        bytes memory signature
    ) external {
        bytes32 messageHash = keccak256(
            abi.encodePacked(tokenId, validator, nonces[validator])
        );
        require(
            _verifySignature(validator, messageHash, signature),
            "SMARTRelayer: invalid signature"
        );

        nonces[validator]++;

        lifecycleContract.validateModelCard(tokenId, validator);

        emit RelayedValidateModelCard(tokenId, validator);
    }

    function relayRejectModelCard(
        uint256 tokenId,
        address rejector,
        string memory reason,
        bytes memory signature
    ) external {
        bytes32 messageHash = keccak256(
            abi.encodePacked(tokenId, rejector, reason, nonces[rejector])
        );
        require(
            _verifySignature(rejector, messageHash, signature),
            "SMARTRelayer: invalid signature"
        );

        nonces[rejector]++;

        lifecycleContract.rejectModelCard(tokenId, reason, rejector);

        emit RelayedRejectModelCard(tokenId, rejector);
    }

    function relayRequestRevision(
        uint256 tokenId,
        address requester,
        string memory feedback,
        bytes memory signature
    ) external {
        bytes32 messageHash = keccak256(
            abi.encodePacked(tokenId, requester, feedback, nonces[requester])
        );
        require(
            _verifySignature(requester, messageHash, signature),
            "SMARTRelayer: invalid signature"
        );

        nonces[requester]++;

        lifecycleContract.requestRevision(tokenId, feedback, requester);

        emit RelayedRequestRevision(tokenId, requester);
    }

    function relayReviseModelCard(
        uint256 tokenId,
        address revisor,
        string memory newMetadataURI,
        bytes32 newContentHash,
        string memory revisionNotes,
        bytes memory signature
    ) external {
        bytes32 messageHash = keccak256(
            abi.encodePacked(
                tokenId,
                revisor,
                newMetadataURI,
                newContentHash,
                revisionNotes,
                nonces[revisor]
            )
        );
        require(
            _verifySignature(revisor, messageHash, signature),
            "SMARTRelayer: invalid signature"
        );

        nonces[revisor]++;

        lifecycleContract.reviseModelCard(tokenId, newMetadataURI, newContentHash, revisionNotes, revisor);

        emit RelayedReviseModelCard(tokenId, revisor);
    }

    function relayPublishModelCard(
        uint256 tokenId,
        address publisher,
        bytes memory signature
    ) external {
        bytes32 messageHash = keccak256(
            abi.encodePacked(tokenId, publisher, nonces[publisher])
        );
        require(
            _verifySignature(publisher, messageHash, signature),
            "SMARTRelayer: invalid signature"
        );

        nonces[publisher]++;

        lifecycleContract.publishModelCard(tokenId, publisher);

        emit RelayedPublishModelCard(tokenId, publisher);
    }

    function relayDeprecateModelCard(
        uint256 tokenId,
        address deprecator,
        string memory reason,
        bytes memory signature
    ) external {
        bytes32 messageHash = keccak256(
            abi.encodePacked(tokenId, deprecator, reason, nonces[deprecator])
        );
        require(
            _verifySignature(deprecator, messageHash, signature),
            "SMARTRelayer: invalid signature"
        );

        nonces[deprecator]++;

        lifecycleContract.deprecateModelCard(tokenId, reason, deprecator);

        emit RelayedDeprecateModelCard(tokenId, deprecator);
    }

    function relayAdminEmergencyPublish(
        uint256 tokenId,
        address admin,
        string memory justification,
        bytes memory signature
    ) external {
        bytes32 messageHash = keccak256(
            abi.encodePacked(tokenId, admin, justification, nonces[admin])
        );
        require(
            _verifySignature(admin, messageHash, signature),
            "SMARTRelayer: invalid signature"
        );

        nonces[admin]++;

        lifecycleContract.adminEmergencyPublish(tokenId, justification, admin);

        emit RelayedAdminEmergencyPublish(tokenId, admin);
    }

    function relayAdminEmergencyDeprecate(
        uint256 tokenId,
        address admin,
        string memory reason,
        string memory justification,
        bytes memory signature
    ) external {
        bytes32 messageHash = keccak256(
            abi.encodePacked(tokenId, admin, reason, justification, nonces[admin])
        );
        require(
            _verifySignature(admin, messageHash, signature),
            "SMARTRelayer: invalid signature"
        );

        nonces[admin]++;

        lifecycleContract.adminEmergencyDeprecate(tokenId, reason, justification, admin);

        emit RelayedAdminEmergencyDeprecate(tokenId, admin);
    }

    function getNonce(address user) external view returns (uint256) {
        return nonces[user];
    }

    function updateLifecycleContract(address _newLifecycle) external onlyOwner {
        require(_newLifecycle != address(0), "SMARTRelayer: invalid address");
        lifecycleContract = ISMARTLifecycle(_newLifecycle);
    }

    function updateAccountFactory(address _newFactory) external onlyOwner {
        require(_newFactory != address(0), "SMARTRelayer: invalid address");
        accountFactory = SMARTAccountFactory(_newFactory);
    }
}
