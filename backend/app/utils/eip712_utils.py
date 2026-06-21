import re
from typing import Any, Dict, List, Union, Tuple
from eth_abi import encode as encode_abi
from eth_account import Account
from eth_typing import Hash32, HexStr
from hexbytes import HexBytes
from web3 import Web3
from eth_utils import to_checksum_address
from eth_account.messages import encode_defunct

def fast_keccak(value: bytes) -> bytes:
    return Web3.keccak(value)

def encode_data(primary_type: str, data: Dict[str, Any], types: Dict[str, List[Dict[str, str]]]) -> bytes:
    encoded_types = ["bytes32"]
    encoded_values = [hash_type(primary_type, types)]

    def _encode_field(name: str, typ: str, value: Any) -> Tuple[str, Any]:
        if typ in types:
            return ["bytes32", fast_keccak(encode_data(typ, value, types))] if value is not None else ["bytes32", b"\x00" * 32]

        if value is None:
            raise ValueError(f"Missing value for field {name} of type {typ}")

        if "uint" in typ or "int" in typ:
            return [typ, int(value)]
        elif typ == "address":
            return ["address", to_checksum_address(value)]
        elif typ == "string":
            return ["bytes32", fast_keccak(value.encode("utf-8"))]
        elif "bytes" in typ:
            return ["bytes32", fast_keccak(HexBytes(value) if isinstance(value, str) else value)]
        elif typ.endswith("]"):
            parsed_type = typ[:typ.rindex("[")]
            type_value_pairs = [_encode_field(name, parsed_type, v) for v in value] if value else ([], [])
            data_types, data_hashes = zip(*type_value_pairs) if type_value_pairs[0] else ([], [])
            return ["bytes32", fast_keccak(encode_abi(data_types, data_hashes))]
        else:
            return [typ, value]

    for field in types[primary_type]:
        typ, val = _encode_field(field["name"], field["type"], data[field["name"]])
        encoded_types.append(typ)
        encoded_values.append(val)

    return encode_abi(encoded_types, encoded_values)

def encode_type(primary_type: str, types: Dict[str, List[Dict[str, str]]]) -> str:
    result = ""
    deps = sorted(set([primary_type] + [d for d in find_type_dependencies(primary_type, types) if d != primary_type]))
    for typ in deps:
        children = types.get(typ)
        if not children:
            raise ValueError(f"No type definition specified for {typ}")
        result += typ + "(" + ",".join(f"{t['type']} {t['name']}" for t in children) + ")"
    return result

def find_type_dependencies(primary_type: str, types: Dict[str, List[Dict[str, str]]], results=None) -> List[str]:
    if results is None:
        results = []

    primary_type = re.split(r"\W", primary_type)[0]
    if primary_type in results or primary_type not in types:
        return results
    results.append(primary_type)

    for field in types[primary_type]:
        find_type_dependencies(field["type"], types, results)
    return results

def hash_type(primary_type: str, types: Dict[str, List[Dict[str, str]]]) -> Hash32:
    return fast_keccak(encode_type(primary_type, types).encode())

def hash_struct(primary_type: str, data: Dict[str, Any], types: Dict[str, List[Dict[str, str]]]) -> Hash32:
    return fast_keccak(encode_data(primary_type, data, types))

def eip712_encode(typed_data: Dict[str, Any]) -> List[bytes]:
    try:
        parts = [
            bytes.fromhex("1901"),
            hash_struct("EIP712Domain", typed_data["domain"], typed_data["types"]),
        ]
        if typed_data["primaryType"] != "EIP712Domain":
            parts.append(
                hash_struct(
                    typed_data["primaryType"],
                    typed_data["message"],
                    typed_data["types"],
                )
            )
        return parts
    except (KeyError, AttributeError, TypeError, IndexError) as exc:
        raise ValueError(f"Not valid typed data for EIP712 encoding: {typed_data}") from exc

def eip712_encode_hash(typed_data: Dict[str, Any]) -> Hash32:
    return fast_keccak(b"".join(eip712_encode(typed_data)))

def eip712_signature(typed_data: Dict[str, Any], private_key: Union[HexStr, bytes]) -> HexStr:
    message_hash_bytes = eip712_encode_hash(typed_data)
    message_hash_hex = message_hash_bytes.hex()
    encoded_message = encode_defunct(hexstr=message_hash_hex)
    account = Account.from_key(private_key)
    signed_message = account.sign_message(encoded_message)
    return '0x' + signed_message.signature.hex()