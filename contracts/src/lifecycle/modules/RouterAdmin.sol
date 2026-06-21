// SPDX-License-Identifier: MIT
pragma solidity ^0.8.27;

import "../libraries/LibRouter.sol";
import "../interfaces/IRouterAdmin.sol";

contract RouterAdmin is IRouterAdmin {
    function routerCut(
        ModuleCut[] calldata _routerCut,
        address _init,
        bytes calldata _calldata
    ) external override {
        LibRouter.enforceIsContractOwner();
        LibRouter.routerCut(_routerCut, _init, _calldata);
    }
}
