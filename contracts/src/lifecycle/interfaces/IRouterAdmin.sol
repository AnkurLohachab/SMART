// SPDX-License-Identifier: MIT
pragma solidity ^0.8.27;

interface IRouterAdmin {
    enum ModuleCutAction {
        Add,
        Replace,
        Remove
    }

    struct ModuleCut {
        address moduleAddress;
        ModuleCutAction action;
        bytes4[] functionSelectors;
    }

    function routerCut(
        ModuleCut[] calldata _routerCut,
        address _init,
        bytes calldata _calldata
    ) external;

    event RouterCut(ModuleCut[] _routerCut, address _init, bytes _calldata);
}
