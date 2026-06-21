// SPDX-License-Identifier: MIT
pragma solidity ^0.8.27;

import "../libraries/LibRouter.sol";
import "../interfaces/IRouterIntrospection.sol";
import "../interfaces/IERC165.sol";

contract RouterIntrospection is IRouterIntrospection, IERC165 {
    function facets() external view override returns (Facet[] memory facets_) {
        LibRouter.RouterStorage storage ds = LibRouter.routerStorage();
        uint256 numFacets = ds.moduleAddresses.length;
        facets_ = new Facet[](numFacets);
        for (uint256 i; i < numFacets; ++i) {
            address facetAddr = ds.moduleAddresses[i];
            facets_[i] = Facet({
                moduleAddress: facetAddr,
                functionSelectors: ds.moduleFunctionSelectors[facetAddr].functionSelectors
            });
        }
    }

    function moduleFunctionSelectors(address _facet)
        external
        view
        override
        returns (bytes4[] memory facetSelectors_)
    {
        facetSelectors_ = LibRouter.routerStorage().moduleFunctionSelectors[_facet].functionSelectors;
    }

    function moduleAddresses() external view override returns (address[] memory addresses_) {
        addresses_ = LibRouter.routerStorage().moduleAddresses;
    }

    function moduleAddress(bytes4 _functionSelector)
        external
        view
        override
        returns (address facet_)
    {
        facet_ = LibRouter
            .routerStorage()
            .selectorToModuleAndPosition[_functionSelector]
            .moduleAddress;
    }

    function supportsInterface(bytes4 _interfaceId) external view override returns (bool) {
        return LibRouter.routerStorage().supportedInterfaces[_interfaceId];
    }
}
