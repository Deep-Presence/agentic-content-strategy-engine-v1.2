"""Service layer protocols and implementations.

Each data domain gets its own Protocol:

- ``GapDataServiceProtocol``   → ``JsonGapDataService``   / ``DbGapDataService``
- ``BrandDataServiceProtocol`` → ``JsonBrandDataService``  / ``DbBrandDataService``
- ``ContentDataServiceProtocol`` → ``JsonContentDataService`` / ``DbContentDataService``

The DI switch in ``api/dependencies.py`` selects the implementation.
"""
