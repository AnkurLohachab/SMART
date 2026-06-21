// SPDX-License-Identifier: MIT
pragma solidity ^0.8.30;

import "@openzeppelin/contracts/token/ERC721/extensions/ERC721URIStorage.sol";
import "@openzeppelin/contracts/token/ERC721/IERC721.sol";
import "@openzeppelin/contracts/access/AccessControl.sol";

interface IERC5484 {
    enum BurnAuth {
        IssuerOnly,
        OwnerOnly,
        Both,
        Neither
    }

    event Issued(
        address indexed from,
        address indexed to,
        uint256 indexed tokenId,
        BurnAuth burnAuth
    );

    function burnAuth(uint256 tokenId) external view returns (BurnAuth);
}

contract SMARTModelCardSBT is ERC721URIStorage, AccessControl, IERC5484 {
    // ============== Role Definitions ==============

    bytes32 public constant MINTER_ROLE = keccak256("MINTER_ROLE");

    bytes32 public constant SBT_ADMIN_ROLE = keccak256("SBT_ADMIN_ROLE");

    // ============== Structs ==============

    struct CardMeta {
        bytes32 cardHash;      // SHA-256 of full model card JSON
        string cid;            // IPFS/Arweave CID pointing to JSON
        string modelVersion;   // e.g., "1.2.0"
        string runId;          // Training/registry run id (MLflow/W&B)
        string schemaVersion;  // SMART model card schema version
        address issuer;        // msg.sender that minted
        uint64 issuedAt;       // block timestamp
        uint256 supersedes;    // tokenId superseded (0 if none)
    }

    // ============== State Variables ==============

    mapping(uint256 => CardMeta) public cardMeta;

    mapping(uint256 => BurnAuth) private _burnAuth;

    mapping(string => uint256) public latestByVersion;

    BurnAuth public defaultBurnAuth;

    uint256 private _nextId = 1;

    // ============== Events ==============

    event CardMinted(
        uint256 indexed tokenId,
        string modelVersion,
        string runId,
        bytes32 cardHash,
        string cid,
        BurnAuth burnAuth
    );

    event CardBurned(
        uint256 indexed tokenId,
        string modelVersion,
        address burnedBy
    );

    event DefaultBurnAuthChanged(
        BurnAuth previousAuth,
        BurnAuth newAuth
    );

    // ============== Constructor ==============

    constructor() ERC721("SMART Model Card SBT", "SMART-SBT") {
        // Grant deployer all admin roles
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
        _grantRole(SBT_ADMIN_ROLE, msg.sender);
        _grantRole(MINTER_ROLE, msg.sender);

        // Default: Both issuer and owner can burn (most flexible for model cards)
        defaultBurnAuth = BurnAuth.Both;
    }

    // ============== Minting ==============

    function mint(
        address to,
        bytes32 cardHash,
        string calldata cid,
        string calldata modelVersion,
        string calldata runId,
        string calldata schemaVersion,
        uint256 supersedesTokenId,
        string calldata tokenURI_
    ) external onlyRole(MINTER_ROLE) returns (uint256) {
        return _mintWithAuth(
            to, cardHash, cid, modelVersion, runId,
            schemaVersion, supersedesTokenId, tokenURI_, defaultBurnAuth
        );
    }

    function mintWithBurnAuth(
        address to,
        bytes32 cardHash,
        string calldata cid,
        string calldata modelVersion,
        string calldata runId,
        string calldata schemaVersion,
        uint256 supersedesTokenId,
        string calldata tokenURI_,
        BurnAuth _burnAuthLevel
    ) external onlyRole(MINTER_ROLE) returns (uint256) {
        return _mintWithAuth(
            to, cardHash, cid, modelVersion, runId,
            schemaVersion, supersedesTokenId, tokenURI_, _burnAuthLevel
        );
    }

    function _mintWithAuth(
        address to,
        bytes32 cardHash,
        string calldata cid,
        string calldata modelVersion,
        string calldata runId,
        string calldata schemaVersion,
        uint256 supersedesTokenId,
        string calldata tokenURI_,
        BurnAuth tokenBurnAuth
    ) internal returns (uint256) {
        require(to != address(0), "SMARTModelCardSBT: mint to zero address");
        require(cardHash != bytes32(0), "SMARTModelCardSBT: empty card hash");
        require(bytes(cid).length > 0, "SMARTModelCardSBT: empty CID");

        uint256 tokenId = _nextId++;
        _safeMint(to, tokenId);
        _setTokenURI(tokenId, tokenURI_);

        cardMeta[tokenId] = CardMeta({
            cardHash: cardHash,
            cid: cid,
            modelVersion: modelVersion,
            runId: runId,
            schemaVersion: schemaVersion,
            issuer: _msgSender(),
            issuedAt: uint64(block.timestamp),
            supersedes: supersedesTokenId
        });

        // Store burn authorization (ERC-5484)
        _burnAuth[tokenId] = tokenBurnAuth;

        // Update latest version tracker
        latestByVersion[modelVersion] = tokenId;

        // Emit ERC-5484 Issued event
        emit Issued(_msgSender(), to, tokenId, tokenBurnAuth);
        emit CardMinted(tokenId, modelVersion, runId, cardHash, cid, tokenBurnAuth);

        return tokenId;
    }

    // ============== Verification Functions ==============

    function verifyCardHash(uint256 tokenId, bytes32 cardHash) external view returns (bool) {
        require(_exists(tokenId), "SMARTModelCardSBT: token does not exist");
        return cardMeta[tokenId].cardHash == cardHash;
    }

    function latestTokenForVersion(string calldata modelVersion) external view returns (uint256) {
        return latestByVersion[modelVersion];
    }

    // ============== ERC-5484: Burn Authorization ==============

    function burnAuth(uint256 tokenId) external view override returns (BurnAuth) {
        require(_exists(tokenId), "SMARTModelCardSBT: token does not exist");
        return _burnAuth[tokenId];
    }

    function burn(uint256 tokenId) external {
        require(_exists(tokenId), "SMARTModelCardSBT: token does not exist");

        BurnAuth auth = _burnAuth[tokenId];
        CardMeta memory meta = cardMeta[tokenId];
        address tokenOwner = ownerOf(tokenId);

        // Check burn authorization per ERC-5484
        if (auth == BurnAuth.Neither) {
            revert("SMARTModelCardSBT: token not burnable");
        } else if (auth == BurnAuth.IssuerOnly) {
            require(
                _msgSender() == meta.issuer || hasRole(SBT_ADMIN_ROLE, _msgSender()),
                "SMARTModelCardSBT: only issuer can burn"
            );
        } else if (auth == BurnAuth.OwnerOnly) {
            require(
                _msgSender() == tokenOwner,
                "SMARTModelCardSBT: only token owner can burn"
            );
        } else if (auth == BurnAuth.Both) {
            require(
                _msgSender() == meta.issuer ||
                _msgSender() == tokenOwner ||
                hasRole(SBT_ADMIN_ROLE, _msgSender()),
                "SMARTModelCardSBT: unauthorized to burn"
            );
        }

        string memory version = meta.modelVersion;
        _burn(tokenId);
        delete cardMeta[tokenId];
        delete _burnAuth[tokenId];

        emit CardBurned(tokenId, version, _msgSender());
    }

    function setDefaultBurnAuth(BurnAuth newDefaultAuth) external onlyRole(SBT_ADMIN_ROLE) {
        BurnAuth previous = defaultBurnAuth;
        defaultBurnAuth = newDefaultAuth;
        emit DefaultBurnAuthChanged(previous, newDefaultAuth);
    }

    // ============== EIP-5192: Soulbound Restrictions ==============

    function locked(uint256 tokenId) external view returns (bool) {
        require(_exists(tokenId), "SMARTModelCardSBT: token does not exist");
        return true;
    }

    function transferFrom(address, address, uint256) public pure override(ERC721, IERC721) {
        revert("SMARTModelCardSBT: soulbound tokens cannot be transferred");
    }

    function safeTransferFrom(address, address, uint256) public pure override(ERC721, IERC721) {
        revert("SMARTModelCardSBT: soulbound tokens cannot be transferred");
    }

    function safeTransferFrom(address, address, uint256, bytes memory) public pure override(ERC721, IERC721) {
        revert("SMARTModelCardSBT: soulbound tokens cannot be transferred");
    }

    // ============== View Functions ==============

    function totalMinted() external view returns (uint256) {
        return _nextId - 1;
    }

    function getCardMeta(uint256 tokenId) external view returns (
        bytes32 cardHash,
        string memory cid,
        string memory modelVersion,
        string memory runId,
        string memory schemaVersion,
        address issuer,
        uint64 issuedAt,
        uint256 supersedes
    ) {
        require(_exists(tokenId), "SMARTModelCardSBT: token does not exist");
        CardMeta memory m = cardMeta[tokenId];
        return (
            m.cardHash, m.cid, m.modelVersion, m.runId,
            m.schemaVersion, m.issuer, m.issuedAt, m.supersedes
        );
    }

    // ============== ERC-165: Interface Detection ==============

    function supportsInterface(bytes4 interfaceId) public view override(ERC721URIStorage, AccessControl) returns (bool) {
        // 0xb45a3c0e = locked(uint256) per EIP-5192
        // 0x0489b56f = burnAuth(uint256) per ERC-5484
        return
            interfaceId == 0xb45a3c0e ||  // EIP-5192
            interfaceId == 0x0489b56f ||  // ERC-5484
            super.supportsInterface(interfaceId);
    }
}
