// SPDX-License-Identifier: MIT
pragma solidity ^0.8.27;

interface IRouterIntrospection {
    struct Facet {
        address moduleAddress;
        bytes4[] functionSelectors;
    }

    function facets() external view returns (Facet[] memory facets_);

    function moduleFunctionSelectors(address _facet)
        external
        view
        returns (bytes4[] memory facetSelectors_);

    function moduleAddresses() external view returns (address[] memory addresses_);

    function moduleAddress(bytes4 _functionSelector)
        external
        view
        returns (address facet_);
}
