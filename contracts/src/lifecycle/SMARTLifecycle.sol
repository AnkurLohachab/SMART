// SPDX-License-Identifier: MIT
pragma solidity ^0.8.27;

import "./libraries/LibRouter.sol";
import "./interfaces/IRouterAdmin.sol";

contract SMARTLifecycle {
    constructor(address _contractOwner, address _routerAdminModule) payable {
        LibRouter.setContractOwner(_contractOwner);

        // Wire up the RouterCut facet so the owner can immediately
        // perform further cuts (Add the Loupe and feature facets).
        bytes4[] memory functionSelectors = new bytes4[](1);
        functionSelectors[0] = IRouterAdmin.routerCut.selector;

        IRouterAdmin.ModuleCut[] memory cut = new IRouterAdmin.ModuleCut[](1);
        cut[0] = IRouterAdmin.ModuleCut({
            moduleAddress: _routerAdminModule,
            action: IRouterAdmin.ModuleCutAction.Add,
            functionSelectors: functionSelectors
        });
        LibRouter.routerCut(cut, address(0), "");
    }

    fallback() external payable {
        LibRouter.RouterStorage storage ds = LibRouter.routerStorage();
        address facet = ds.selectorToModuleAndPosition[msg.sig].moduleAddress;
        require(facet != address(0), "Router: function does not exist");
        assembly {
            calldatacopy(0, 0, calldatasize())
            let result := delegatecall(gas(), facet, 0, calldatasize(), 0, 0)
            returndatacopy(0, 0, returndatasize())
            switch result
            case 0 {
                revert(0, returndatasize())
            }
            default {
                return(0, returndatasize())
            }
        }
    }

    receive() external payable {}
}
