// SPDX-License-Identifier: MIT
pragma solidity ^0.8.27;

import "../interfaces/IRouterAdmin.sol";

library LibRouter {
    bytes32 internal constant DIAMOND_STORAGE_POSITION =
        keccak256("diamond.standard.diamond.storage");

    struct ModuleAddressAndPosition {
        address moduleAddress;
        uint96 functionSelectorPosition; // index in moduleFunctionSelectors.functionSelectors
    }

    struct ModuleFunctionSelectors {
        bytes4[] functionSelectors;
        uint256 moduleAddressPosition; // index in moduleAddresses
    }

    struct RouterStorage {
        // selector → facet + position-in-facet
        mapping(bytes4 => ModuleAddressAndPosition) selectorToModuleAndPosition;
        // facet → selectors + position-in-moduleAddresses
        mapping(address => ModuleFunctionSelectors) moduleFunctionSelectors;
        // all facet addresses
        address[] moduleAddresses;
        // ERC-165
        mapping(bytes4 => bool) supportedInterfaces;
        // owner
        address contractOwner;
    }

    error NotContractOwner(address sender, address owner);
    error NoSelectorsInFacet();
    error CannotAddFunctionThatExists(bytes4 selector);
    error CannotReplaceFunctionThatDoesNotExist(bytes4 selector);
    error CannotReplaceFunctionWithSameAddress(bytes4 selector);
    error CannotRemoveFunctionThatDoesNotExist(bytes4 selector);
    error CannotRemoveImmutableFunction(bytes4 selector);
    error InitFunctionReverted(address init, bytes data);
    error AddressHasNoCode(address target);

    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);

    function routerStorage() internal pure returns (RouterStorage storage ds) {
        bytes32 position = DIAMOND_STORAGE_POSITION;
        assembly {
            ds.slot := position
        }
    }

    function setContractOwner(address _newOwner) internal {
        RouterStorage storage ds = routerStorage();
        address previousOwner = ds.contractOwner;
        ds.contractOwner = _newOwner;
        emit OwnershipTransferred(previousOwner, _newOwner);
    }

    function contractOwner() internal view returns (address) {
        return routerStorage().contractOwner;
    }

    function enforceIsContractOwner() internal view {
        if (msg.sender != routerStorage().contractOwner) {
            revert NotContractOwner(msg.sender, routerStorage().contractOwner);
        }
    }

    function routerCut(
        IRouterAdmin.ModuleCut[] memory _routerCut,
        address _init,
        bytes memory _calldata
    ) internal {
        for (uint256 moduleIndex; moduleIndex < _routerCut.length; ++moduleIndex) {
            IRouterAdmin.ModuleCutAction action = _routerCut[moduleIndex].action;
            if (action == IRouterAdmin.ModuleCutAction.Add) {
                addFunctions(_routerCut[moduleIndex].moduleAddress, _routerCut[moduleIndex].functionSelectors);
            } else if (action == IRouterAdmin.ModuleCutAction.Replace) {
                replaceFunctions(_routerCut[moduleIndex].moduleAddress, _routerCut[moduleIndex].functionSelectors);
            } else if (action == IRouterAdmin.ModuleCutAction.Remove) {
                removeFunctions(_routerCut[moduleIndex].moduleAddress, _routerCut[moduleIndex].functionSelectors);
            }
        }
        emit IRouterAdmin.RouterCut(_routerCut, _init, _calldata);
        initializeRouterCut(_init, _calldata);
    }

    function addFunctions(address _moduleAddress, bytes4[] memory _selectors) internal {
        if (_selectors.length == 0) revert NoSelectorsInFacet();
        RouterStorage storage ds = routerStorage();
        if (_moduleAddress == address(0)) revert AddressHasNoCode(_moduleAddress);
        uint96 selectorPosition = uint96(ds.moduleFunctionSelectors[_moduleAddress].functionSelectors.length);
        if (selectorPosition == 0) {
            addModule(ds, _moduleAddress);
        }
        for (uint256 i; i < _selectors.length; ++i) {
            bytes4 sel = _selectors[i];
            address oldFacet = ds.selectorToModuleAndPosition[sel].moduleAddress;
            if (oldFacet != address(0)) revert CannotAddFunctionThatExists(sel);
            addFunction(ds, sel, selectorPosition, _moduleAddress);
            ++selectorPosition;
        }
    }

    function replaceFunctions(address _moduleAddress, bytes4[] memory _selectors) internal {
        if (_selectors.length == 0) revert NoSelectorsInFacet();
        RouterStorage storage ds = routerStorage();
        if (_moduleAddress == address(0)) revert AddressHasNoCode(_moduleAddress);
        uint96 selectorPosition = uint96(ds.moduleFunctionSelectors[_moduleAddress].functionSelectors.length);
        if (selectorPosition == 0) {
            addModule(ds, _moduleAddress);
        }
        for (uint256 i; i < _selectors.length; ++i) {
            bytes4 sel = _selectors[i];
            address oldFacet = ds.selectorToModuleAndPosition[sel].moduleAddress;
            if (oldFacet == _moduleAddress) revert CannotReplaceFunctionWithSameAddress(sel);
            if (oldFacet == address(0)) revert CannotReplaceFunctionThatDoesNotExist(sel);
            removeFunction(ds, oldFacet, sel);
            addFunction(ds, sel, selectorPosition, _moduleAddress);
            ++selectorPosition;
        }
    }

    function removeFunctions(address _moduleAddress, bytes4[] memory _selectors) internal {
        if (_selectors.length == 0) revert NoSelectorsInFacet();
        RouterStorage storage ds = routerStorage();
        // _moduleAddress must be address(0) for removal per spec
        for (uint256 i; i < _selectors.length; ++i) {
            bytes4 sel = _selectors[i];
            address oldFacet = ds.selectorToModuleAndPosition[sel].moduleAddress;
            if (oldFacet == address(0)) revert CannotRemoveFunctionThatDoesNotExist(sel);
            // immutable function = function provided by the diamond itself
            if (oldFacet == address(this)) revert CannotRemoveImmutableFunction(sel);
            removeFunction(ds, oldFacet, sel);
        }
    }

    function addModule(RouterStorage storage ds, address _moduleAddress) internal {
        if (_moduleAddress.code.length == 0) revert AddressHasNoCode(_moduleAddress);
        ds.moduleFunctionSelectors[_moduleAddress].moduleAddressPosition = ds.moduleAddresses.length;
        ds.moduleAddresses.push(_moduleAddress);
    }

    function addFunction(
        RouterStorage storage ds,
        bytes4 _selector,
        uint96 _selectorPosition,
        address _moduleAddress
    ) internal {
        ds.selectorToModuleAndPosition[_selector] = ModuleAddressAndPosition({
            moduleAddress: _moduleAddress,
            functionSelectorPosition: _selectorPosition
        });
        ds.moduleFunctionSelectors[_moduleAddress].functionSelectors.push(_selector);
    }

    function removeFunction(
        RouterStorage storage ds,
        address _moduleAddress,
        bytes4 _selector
    ) internal {
        if (_moduleAddress == address(0)) revert CannotRemoveFunctionThatDoesNotExist(_selector);
        // replace selector with last selector then pop
        uint256 selectorPosition = ds.selectorToModuleAndPosition[_selector].functionSelectorPosition;
        uint256 lastSelectorPosition = ds.moduleFunctionSelectors[_moduleAddress].functionSelectors.length - 1;
        if (selectorPosition != lastSelectorPosition) {
            bytes4 lastSelector = ds.moduleFunctionSelectors[_moduleAddress].functionSelectors[lastSelectorPosition];
            ds.moduleFunctionSelectors[_moduleAddress].functionSelectors[selectorPosition] = lastSelector;
            ds.selectorToModuleAndPosition[lastSelector].functionSelectorPosition = uint96(selectorPosition);
        }
        ds.moduleFunctionSelectors[_moduleAddress].functionSelectors.pop();
        delete ds.selectorToModuleAndPosition[_selector];
        // If the facet has no more selectors, remove it from moduleAddresses.
        if (lastSelectorPosition == 0) {
            uint256 moduleAddressPosition = ds.moduleFunctionSelectors[_moduleAddress].moduleAddressPosition;
            uint256 lastFacetAddressPosition = ds.moduleAddresses.length - 1;
            if (moduleAddressPosition != lastFacetAddressPosition) {
                address lastFacet = ds.moduleAddresses[lastFacetAddressPosition];
                ds.moduleAddresses[moduleAddressPosition] = lastFacet;
                ds.moduleFunctionSelectors[lastFacet].moduleAddressPosition = moduleAddressPosition;
            }
            ds.moduleAddresses.pop();
            delete ds.moduleFunctionSelectors[_moduleAddress].moduleAddressPosition;
        }
    }

    function initializeRouterCut(address _init, bytes memory _calldata) internal {
        if (_init == address(0)) {
            return;
        }
        if (_init.code.length == 0) revert AddressHasNoCode(_init);
        (bool ok, bytes memory ret) = _init.delegatecall(_calldata);
        if (!ok) {
            if (ret.length > 0) {
                assembly {
                    let returndata_size := mload(ret)
                    revert(add(32, ret), returndata_size)
                }
            } else {
                revert InitFunctionReverted(_init, _calldata);
            }
        }
    }
}
