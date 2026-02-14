# Bugs

- Low Test Coverage

  Low Coverage Modules:
  app/routes/tasks.py: 14% (needs integration tests with authentication)
  app/routes/health.py: 31%
  app/routes/state.py: 32%
  app/routes/version.py: 31%
  app/services/health_check.py: 15%
  app/services/authorization.py: 53%
  app/services/data_export.py: 42%

- **Severity**: Medium
- **Location**: Core application modules
- **Status**: Add tests for task_registry.py (100% coverage), improved experimental_tasks.py coverage
- **Reproduction Steps**: Run `pytest --cov=app --cov-report=term-missing`
- **Expected Behavior**: >80% test coverage for critical paths
- **Actual Behavior**: Coverage improved for task modules, additional tests can be added as needed
- **Impact**: Better test coverage for core functionality
