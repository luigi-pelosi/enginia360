"""Compatibilità del comando di verifica RBAC con lo schema finale.

Le prove di traduzione di grant storici sono archiviate fuori repository insieme
alle migrazioni ritirate. Audit, catalogo corrente e assenza di escalation sono
verificati dalla suite dbbaseline sul solo cluster effimero esplicito.
"""
import unittest
from test_dbbaseline import BaselineInvariantTests

if __name__ == '__main__':
    unittest.main(verbosity=2)
