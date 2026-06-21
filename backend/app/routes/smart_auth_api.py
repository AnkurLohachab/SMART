
from fastapi import APIRouter, HTTPException, Depends, Header
from fastapi.responses import JSONResponse
from app.models import UserRegistrationRequest, UserVerifyRequest, AuthenticateRequest, AuthenticateResponse, LoginResponse, LoginRequest, UploadModelCardRequest, UploadModelCardResponse, WalletInfo, UserProfileUpdateRequest
from app.config import settings
from app.utils import smart_chain
from web3 import Web3, HTTPProvider
from eth_utils import to_checksum_address, is_address
import logging
import uuid
import secrets
from app.db import neo4j_conn
import time
import json
from app.utils.eip712_utils import eip712_encode_hash, eip712_signature
from app.utils.auth import get_current_user, TokenData
from app.utils.minio_utils import upload_model_card_json
from typing import Any, Dict

logger = logging.getLogger("backend.smart_auth_api")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
handler.setFormatter(formatter)
if not logger.handlers:
    logger.addHandler(handler)

router = APIRouter()

w3 = Web3(HTTPProvider(settings.INFURA_URL))
if not w3.is_connected():
    logger.error("Web3 is not connected. Check the provider URI.")
    raise ConnectionError("Web3 is not connected.")


@router.post("/register", status_code=201)
async def register(user: UserRegistrationRequest):
    """Start registration: generate EOA/SmartID/OTP, store in Neo4j, send the OTP."""
    try:
        user_uuid = user.uuid or str(uuid.uuid4())

        logger.info(f"Initiating SMART registration for UUID: {user_uuid}")

        existing_user = await neo4j_conn.get_user_by_uuid(user_uuid)

        if existing_user:
            eoa_address = existing_user.get("eoa_address")
            is_verified = existing_user.get("verified", False)

            if is_verified:
                logger.warning(
                    f"Registration attempt with already verified UUID: {user_uuid}, EOA: {eoa_address}"
                )
                raise HTTPException(
                    status_code=400, detail="UUID is already registered and verified."
                )
            else:
                logger.info(
                    f"UUID '{user_uuid}' exists but not verified. Checking blockchain registration."
                )

                is_registered_on_chain = await smart_chain.check_if_registered(eoa_address)
                if is_registered_on_chain:
                    logger.warning(
                        f"User with UUID '{user_uuid}' and EOA '{eoa_address}' is already registered on the blockchain."
                    )
                    raise HTTPException(
                        status_code=400, detail="User is already registered on the blockchain."
                    )

                otp = secrets.randbelow(1000000)
                otp_code = f"{otp:06}"

                otp_expires_at = time.time() + settings.OTP_EXPIRY_SECONDS
                logger.debug(f"OTP expiration time: {otp_expires_at}")

                await neo4j_conn.update_otp(user_uuid, otp_code, otp_expires_at)
                logger.info(f"Updated OTP for UUID '{user_uuid}' in Neo4j.")

                smart_id = f"{eoa_address}_{user_uuid}"
                registration_payload = {
                    "types": {
                        "EIP712Domain": [
                            {"name": "name", "type": "string"},
                            {"name": "version", "type": "string"},
                            {"name": "chainId", "type": "uint256"},
                            {"name": "verifyingContract", "type": "address"},
                        ],
                        "Register": [
                            {"name": "eoa", "type": "address"},
                            {"name": "smartId", "type": "string"},
                            {"name": "factory", "type": "address"},
                        ],
                    },
                    "primaryType": "Register",
                    "domain": {
                        "name": "SMARTAccountFactory",
                        "version": "1",
                        "chainId": int(settings.CHAIN_ID),
                        "verifyingContract": to_checksum_address(settings.SMART_ACCOUNT_FACTORY_ADDRESS),
                    },
                    "message": {
                        "eoa": to_checksum_address(eoa_address),
                        "smartId": smart_id,
                        "factory": to_checksum_address(settings.SMART_ACCOUNT_FACTORY_ADDRESS),
                    },
                }

                logger.debug(f"EIP-712 Register payload: {json.dumps(registration_payload, indent=2)}")

                user_private_key = await neo4j_conn.get_private_key(user_uuid)
                if not user_private_key:
                    logger.error(f"No private key found for UUID '{user_uuid}'.")
                    raise HTTPException(status_code=400, detail="Private key not found for the user.")

                signature_generated = eip712_signature(registration_payload, user_private_key)
                logger.debug(f"Generated signature: {signature_generated}")

                is_signature_valid = await smart_chain.verify_signature(registration_payload, signature_generated)
                logger.info(f"Signature verification result for UUID '{user_uuid}': {is_signature_valid}")

                await neo4j_conn.update_signature(user_uuid, signature_generated, is_signature_valid)
                logger.info(f"Updated signature status for UUID '{user_uuid}' in Neo4j.")

                response_content = {
                    "message": "Registration initiated. Please verify using the OTP sent.",
                    "otp": otp_code,
                    "uuid": user_uuid,
                }

                return JSONResponse(status_code=201, content=response_content)

        else:
            account = w3.eth.account.create()
            eoa_address = account.address
            private_key = account.key.hex()

            logger.debug(f"Generated EOA: {eoa_address}")

            is_registered_on_chain = await smart_chain.check_if_registered(eoa_address)
            if is_registered_on_chain:
                logger.warning(f"EOA already registered on blockchain: {eoa_address}")
                raise HTTPException(
                    status_code=400, detail="EOA is already registered on the blockchain."
                )

            smart_id = f"{eoa_address}_{user_uuid}"
            logger.debug(f"Generated SmartID: {smart_id}")

            otp = secrets.randbelow(1000000)
            otp_code = f"{otp:06}"

            otp_expires_at = time.time() + settings.OTP_EXPIRY_SECONDS
            logger.debug(f"OTP expiration time: {otp_expires_at}")

            registration_payload = {
                "types": {
                    "EIP712Domain": [
                        {"name": "name", "type": "string"},
                        {"name": "version", "type": "string"},
                        {"name": "chainId", "type": "uint256"},
                        {"name": "verifyingContract", "type": "address"},
                    ],
                    "Register": [
                        {"name": "eoa", "type": "address"},
                        {"name": "smartId", "type": "string"},
                        {"name": "factory", "type": "address"},
                    ],
                },
                "primaryType": "Register",
                "domain": {
                    "name": "SMARTAccountFactory",
                    "version": "1",
                    "chainId": int(settings.CHAIN_ID),
                    "verifyingContract": to_checksum_address(settings.SMART_ACCOUNT_FACTORY_ADDRESS),
                },
                "message": {
                    "eoa": to_checksum_address(eoa_address),
                    "smartId": smart_id,
                    "factory": to_checksum_address(settings.SMART_ACCOUNT_FACTORY_ADDRESS),
                },
            }

            logger.debug(f"EIP-712 Register payload: {json.dumps(registration_payload, indent=2)}")

            signature_generated = eip712_signature(registration_payload, private_key)
            logger.debug(f"Generated signature: {signature_generated}")

            await neo4j_conn.create_user(
                uuid=user_uuid,
                eoa_address=eoa_address,
                smart_id=smart_id,
                otp=otp_code,
                otp_expires_at=otp_expires_at,
                private_key=private_key,
                signature=signature_generated,
                signature_verified=False,
                username=user.username,
                email=user.email,
            )
            logger.info(
                f"Stored EOA '{eoa_address}', UUID '{user_uuid}', SmartID '{smart_id}' in Neo4j."
            )

            response_content = {
                "message": "Registration initiated. Please verify using the OTP sent.",
                "otp": otp_code,
                "uuid": user_uuid,
            }

            return JSONResponse(status_code=201, content=response_content)

    except HTTPException as he:
        logger.error(f"HTTPException during registration: {he.detail}")
        raise he
    except Exception as e:
        logger.exception(f"Unexpected error during registration: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/verify", status_code=200)
async def verify(user_verify: UserVerifyRequest):
    """Verify the user's OTP/UUID, create SMARTAccounts, and return roles and accounts."""
    try:
        user_uuid = user_verify.uuid
        otp = user_verify.otp

        logger.info(f"Verifying OTP for UUID: {user_uuid}")

        user = await neo4j_conn.get_user_by_uuid(user_uuid)
        if not user:
            logger.error(f"No user found with UUID '{user_uuid}'.")
            raise HTTPException(status_code=404, detail="User not found.")

        eoa_address = user.get("eoa_address")
        if not eoa_address:
            logger.error(f"No EOA address found for UUID '{user_uuid}'.")
            raise HTTPException(status_code=400, detail="EOA address not found for the user.")

        is_valid_otp = await neo4j_conn.verify_otp(user_uuid, otp)
        if not is_valid_otp:
            logger.warning(f"Invalid or expired OTP '{otp}' for UUID '{user_uuid}'.")
            raise HTTPException(status_code=400, detail="Invalid or expired OTP.")

        logger.info(f"OTP '{otp}' for UUID '{user_uuid}' is valid.")

        smart_id = user.get("smart_id") or user.get("luceid")
        if not smart_id:
            logger.error(f"SmartID not found for UUID '{user_uuid}'.")
            raise HTTPException(status_code=400, detail="SmartID not found for the user.")

        smart_accounts = await smart_chain.create_account_with_username_gasless(eoa_address, smart_id)
        if not smart_accounts:
            logger.error(f"Failed to create SMARTAccounts for UUID '{user_uuid}'.")
            raise HTTPException(status_code=500, detail="Failed to create SMARTAccounts.")

        logger.info(f"SMARTAccounts created for UUID '{user_uuid}': {smart_accounts}")

        for role, address in smart_accounts.items():
            await neo4j_conn.store_smart_account(user_uuid, address, role)
            logger.info(f"Stored SMARTAccount '{address}' with role '{role}' for UUID '{user_uuid}'.")

        roles = await neo4j_conn.get_user_roles(user_uuid)
        if not roles:
            logger.warning(f"No roles found for UUID '{user_uuid}'. Assigning default roles.")
            roles = ["Reader", "AIDeveloper"]

        smart_accounts_db = await neo4j_conn.get_smart_accounts(user_uuid)
        smart_account_addresses = [acc['address'] for acc in smart_accounts_db]

        identity_claims_issued = []
        try:
            from app.utils.identity_binding import (
                issue_self_attested_claims_for_role,
                ROLE_TO_CLAIM_TYPES,
            )
            primary_role = next(
                (r for r in roles if r in ROLE_TO_CLAIM_TYPES and ROLE_TO_CLAIM_TYPES[r]),
                None,
            )
            if primary_role:
                results = issue_self_attested_claims_for_role(eoa_address, primary_role)
                identity_claims_issued = [
                    {
                        "claim_type": r.get("claim_type"),
                        "tx_hash": r.get("tx_hash"),
                        "error": r.get("error"),
                    }
                    for r in results
                ]
                logger.info(
                    "Issued self-attested claims for UUID '%s' (role=%s): %s",
                    user_uuid, primary_role, identity_claims_issued,
                )
        except Exception as ic_err:
            logger.warning("self-attested claim issuance failed for %s: %s", eoa_address, ic_err)

        response_content = {
            "message": "Verification successful. You are now logged in.",
            "roles": roles,
            "smart_accounts": smart_account_addresses,
            "identity_claims_issued": identity_claims_issued,
        }

        return JSONResponse(status_code=200, content=response_content)

    except HTTPException as he:
        logger.error(f"HTTPException during verification: {he.detail}")
        raise he
    except Exception as e:
        logger.exception(f"Unexpected error during verification: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Login with UUID and selected role; returns an OTP."""
    user_uuid = request.uuid
    selected_role = request.role

    logger.info(f"Login attempt for UUID: {user_uuid} with role: {selected_role}")

    user = await neo4j_conn.get_user_by_uuid(user_uuid)
    if not user:
        logger.warning(f"Login attempt with unregistered UUID: {user_uuid}")
        raise HTTPException(status_code=400, detail="You are not registered.")

    user_roles = await neo4j_conn.get_user_roles(user_uuid)
    if selected_role not in user_roles:
        logger.warning(f"User '{user_uuid}' attempted to login with invalid role: {selected_role}")
        raise HTTPException(status_code=400, detail="Selected role is invalid.")

    smart_accounts = await neo4j_conn.get_smart_accounts(user_uuid)
    associated_accounts = [acc for acc in smart_accounts if acc['role'] == selected_role]

    if not associated_accounts:
        logger.warning(f"No SMARTAccount found for User '{user_uuid}' with role '{selected_role}'.")
        raise HTTPException(status_code=400, detail="No SMARTAccount associated with the selected role.")

    smart_account = associated_accounts[0]
    smart_account_address = smart_account['address']

    is_registered = await smart_chain.is_registered_smart_account(smart_account_address)
    if not is_registered:
        logger.warning(f"SMARTAccount '{smart_account_address}' for User '{user_uuid}' is not registered.")
        raise HTTPException(status_code=400, detail="Selected role's SMARTAccount is not registered.")

    otp = secrets.token_hex(3)
    otp_expires_at = time.time() + settings.OTP_EXPIRY_SECONDS

    await neo4j_conn.update_otp(user_uuid, otp, otp_expires_at)

    logger.info(f"OTP generated for User '{user_uuid}' with role '{selected_role}': {otp}")

    return LoginResponse(message="OTP has been generated and sent.", otp=otp)


@router.post("/authenticate", response_model=AuthenticateResponse)
async def authenticate(request: AuthenticateRequest):
    """Authenticate with UUID, role, and OTP; returns a session token."""
    try:
        user_uuid = request.uuid
        selected_role = request.role
        otp = request.otp

        logger.info(f"Authentication attempt for UUID: {user_uuid} with role: {selected_role}")

        user = await neo4j_conn.get_user_by_uuid(user_uuid)
        if not user:
            logger.warning(f"Authentication attempt with unregistered UUID: {user_uuid}")
            raise HTTPException(status_code=400, detail="You are not registered.")

        is_valid_otp = await neo4j_conn.verify_otp(user_uuid, otp)
        if not is_valid_otp:
            logger.warning(f"Invalid or expired OTP '{otp}' for UUID '{user_uuid}'.")
            raise HTTPException(status_code=400, detail="Invalid or expired OTP.")

        user_roles = await neo4j_conn.get_user_roles(user_uuid)
        if selected_role not in user_roles:
            logger.warning(f"User '{user_uuid}' attempted to authenticate with invalid role: {selected_role}")
            raise HTTPException(status_code=400, detail="Selected role is invalid.")

        auth_token = secrets.token_urlsafe(32)

        token_expires_at = time.time() + settings.TOKEN_EXPIRY_SECONDS
        logger.debug(f"Token expiration time: {token_expires_at}")

        await neo4j_conn.store_auth_token(user_uuid, auth_token, token_expires_at)
        logger.info(f"Stored auth token for UUID '{user_uuid}'.")

        await neo4j_conn.set_signature_verified(user_uuid, True)
        logger.info(f"Signature verified status set to 'True' for UUID '{user_uuid}'.")

        eoa_address = user.get("eoa_address")
        smart_accounts = await neo4j_conn.get_smart_accounts(user_uuid)

        smart_account_address = None
        for acc in smart_accounts:
            if acc.get("role") == selected_role:
                smart_account_address = acc.get("address")
                break

        wallet_info = WalletInfo(
            eoa_address=eoa_address,
            smart_account=smart_account_address,
            role=selected_role
        )

        logger.info(f"Returning wallet info for UUID '{user_uuid}': EOA={eoa_address}, SMARTAccount={smart_account_address}")

        return AuthenticateResponse(
            message="Authentication successful.",
            token=auth_token,
            wallet_info=wallet_info
        )

    except HTTPException as he:
        logger.error(f"HTTPException during authentication: {he.detail}")
        raise he
    except Exception as e:
        logger.exception(f"Unexpected error during authentication: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/upload-model-card", response_model=UploadModelCardResponse, status_code=201)
async def upload_model_card(
    upload_request: UploadModelCardRequest,
    current_user: Any = Depends(get_current_user)
):
    """Upload a model card JSON to MinIO, mint it on-chain via the relayer, and log it in Neo4j."""
    try:
        if not is_address(upload_request.custom_account):
            logger.error(f"Invalid SMARTAccount address: {upload_request.custom_account}")
            raise HTTPException(status_code=400, detail="Invalid SMARTAccount address.")

        smart_account = to_checksum_address(upload_request.custom_account)

        user_uuid = current_user.uuid
        if not user_uuid:
            logger.error("Authenticated user does not have a UUID.")
            raise HTTPException(status_code=400, detail="User UUID not found.")

        associated_accounts = await neo4j_conn.get_smart_accounts(user_uuid)
        if smart_account not in [acc["address"] for acc in associated_accounts]:
            logger.error(f"SMARTAccount '{smart_account}' does not belong to user '{user_uuid}'.")
            raise HTTPException(status_code=403, detail="SMARTAccount does not belong to the user.")

        storage_url = upload_model_card_json(upload_request.model_data, user_uuid)
        logger.info(f"Model card JSON uploaded to MinIO at '{storage_url}'.")

        model_id = upload_request.model_data.get("id")
        model_name = upload_request.model_data.get("name")
        model_json = json.dumps(upload_request.model_data)

        if not model_id or not model_name:
            logger.error("Model data must include 'id' and 'name' fields.")
            raise HTTPException(status_code=400, detail="Model data must include 'id' and 'name' fields.")

        response = await smart_chain.create_model_card_gasless(
            smart_account=smart_account,
            token_id=model_id,
            data=model_json,
            name=model_name
        )

        if not response["success"]:
            logger.error(f"Smart contract interaction failed: {response['error']}")
            raise HTTPException(status_code=500, detail="Failed to create model card on blockchain.")

        token_id = response["token_id"]
        logger.info(f"Model card created on blockchain with token ID '{token_id}'.")

        await neo4j_conn.log_model_card_upload(
            smart_account=smart_account,
            token_id=token_id,
            storage_url=storage_url,
            model_data=upload_request.model_data
        )
        logger.info(f"Model card upload logged in Neo4j for token ID '{token_id}'.")

        upload_response = UploadModelCardResponse(
            message="Model card uploaded and created successfully.",
            token_id=token_id,
            storage_url=storage_url
        )

        return upload_response

    except HTTPException as he:
        logger.error(f"HTTPException during model card upload: {he.detail}")
        raise he
    except Exception as e:
        logger.exception(f"Unexpected error during model card upload: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/logout", status_code=200)
async def logout(token: str = Header(None)):
    """Invalidate the user's authentication token."""
    try:
        if not token:
            raise HTTPException(status_code=400, detail="Authentication token is missing.")

        await neo4j_conn.invalidate_token(token)
        logger.info(f"Authentication token has been invalidated.")

        return JSONResponse(status_code=200, content={"message": "Successfully logged out."})

    except HTTPException as he:
        logger.error(f"HTTPException during logout: {he.detail}")
        raise he
    except Exception as e:
        logger.exception(f"Unexpected error during logout: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/user/{uuid}")
async def get_user_info(uuid: str):
    """Get user info: wallet addresses, profile fields, and role-bound SMARTAccount."""
    try:
        user = await neo4j_conn.get_user_by_uuid(uuid)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        role = user.get("role")
        smart_accounts = await neo4j_conn.get_smart_accounts(uuid)
        smart_account = next(
            (a["address"] for a in smart_accounts if a.get("role") == role),
            smart_accounts[0]["address"] if smart_accounts else None,
        )
        try:
            roles = await neo4j_conn.get_user_roles(uuid)
        except Exception:
            roles = [role] if role else []

        return {
            "uuid": uuid,
            "eoa_address": user.get("eoa_address"),
            "smart_account": smart_account,
            "smart_accounts": smart_accounts,
            "role": role,
            "roles": roles,
            "username": user.get("username"),
            "email": user.get("email"),
            "created_at": user.get("created_at"),
            "status": user.get("status"),
            "verified": user.get("verified"),
            "smart_id": user.get("smart_id"),
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.exception(f"Unexpected error getting user info: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/role-requests/mine")
async def get_my_role_requests(uuid: str):
    """Return this user's role-request history (all statuses), newest first."""
    try:
        user = await neo4j_conn.get_user_by_uuid(uuid)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        rows = await neo4j_conn.get_user_role_requests(uuid)
        return {"requests": rows}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error fetching role requests for '{uuid}': {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/user/{uuid}/profile")
async def update_user_profile(
    uuid: str,
    payload: UserProfileUpdateRequest,
    current_user: Any = Depends(get_current_user),
):
    """Update profile fields (username, email) for the authenticated user."""
    if current_user.uuid != uuid:
        raise HTTPException(status_code=403, detail="Cannot edit another user's profile.")
    try:
        username = payload.username.strip() if payload.username else None
        email = payload.email.strip() if payload.email else None
        if username == "":
            username = None
        if email == "":
            email = None

        existed = await neo4j_conn.update_user_profile(uuid, username=username, email=email)
        if not existed:
            raise HTTPException(status_code=404, detail="User not found")

        return await get_user_info(uuid)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error updating profile: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
