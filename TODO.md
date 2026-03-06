## Test Coverage Gaps

### Coverage Summary by Module

| Module | Statements | Covered | Missing | Coverage % | Status |
|--------|-----------|---------|---------|-----------|--------|
| `app/routes/api_keys.py` | 112 | 108 | 4 | **96%** | � |
| `app/routes/webhooks.py` | 69 | 69 | 0 | **100%** | � |
| `app/services/webhook_manager.py` | 149 | 108 | 41 | **72%** | 🟡 |
| `app/services/error_recovery.py` | 152 | 148 | 4 | **97%** | � |
| `app/services/sharding_service.py` | 63 | 0 | 63 | **0%** | 🔴 |
| `app/services/seeding_service.py` | 163 | 0 | 163 | **0%** | 🔴 |
| `app/tasks/experimental_tasks.py` | 171 | 60 | 111 | **35%** | 🟠 |
| `app/tasks/task_registry.py` | 27 | 27 | 0 | **100%** | � |
| `app/tracing.py` | 50 | 0 | 50 | **0%** | 🔴 |
| `app/database/sharded_connection.py` | 94 | 0 | 94 | **0%** | 🔴 |
| `app/cli.py` | 90 | 0 | 90 | **0%** | 🔴 |
| `app/middleware/schema_validation.py` | 158 | 18 | 140 | **11%** | 🔴 |
| `app/services/session_manager.py` | 359 | 279 | 80 | **78%** | 🟡 |
| `app/services/rate_limiter.py` | 44 | 11 | 33 | **25%** | 🔴 |
| `app/middleware/tracing.py` | 77 | 20 | 57 | **26%** | 🔴 |
| `app/middleware/alerting.py` | 293 | 146 | 147 | **50%** | � |
| `app/routes/sessions.py` | 174 | 49 | 125 | **28%** | 🔴 |
| `app/middleware/csrf.py` | 63 | 16 | 47 | **25%** | 🔴 |
| `app/middleware/authentication.py` | 115 | 95 | 20 | **83%** | � |
| `app/services/auth_manager.py` | 249 | 95 | 154 | **38%** | 🟠 |
| `app/routes/tasks.py` | 166 | 77 | 89 | **46%** | � |
| `app/routes/state.py` | 146 | 51 | 95 | **35%** | � |
| `app/routes/templates.py` | 140 | 23 | 117 | **16%** | 🔴 |
| `app/models/schemas.py` | 693 | 509 | 184 | **73%** | 🟡 |
| `app/config.py` | 153 | 128 | 25 | **84%** | � |
| `app/routes/api_keys.py` | 96% | 80% | 0% | � Good |
| `app/routes/webhooks.py` | 100% | 80% | 0% | � Good |
| `app/services/webhook_manager.py` | 72% | 80% | 8% | � High |
| `app/services/error_recovery.py` | 97% | 80% | 0% | � Good |
| `app/tasks/experimental_tasks.py` | 35% | 70% | 35% | � High |
| `app/middleware/authentication.py` | 83% | 80% | 0% | � Good |
| `app/services/session_manager.py` | 78% | 80% | 2% | � High |
| `app/routes/tasks.py` | 46% | 80% | 34% | � High |
| `app/routes/state.py` | 35% | 80% | 45% | � High |
| `app/services/auth_manager.py` | 38% | 80% | 42% | 🟠 High |
| `app/middleware/csrf.py` | 25% | 80% | 55% | � Critical |
| `app/middleware/rate_limiting.py` | 37% | 80% | 43% | 🟠 High |
| `app/services/cache_service.py` | 37% | 80% | 43% | 🟠 High |

---------- coverage: platform darwin, python 3.14.3-final-0 ----------
Name                                   Stmts   Miss  Cover   Missing
--------------------------------------------------------------------
app/__init__.py                            1      0   100%
app/celery_app.py                         16      3    81%   24, 28, 31
app/cli.py                                90     90     0%   7-173
app/config.py                            153     25    84%   32, 128, 206, 226, 229, 256, 277-285, 293-306, 328, 346-348, 353-355, 360-362
app/database/__init__.py                   3      0   100%
app/database/connection.py                97     42    57%   26, 59-61, 74-75, 92-94, 118-151, 220-251, 258-259
app/database/models.py                   164      0   100%
app/database/sharded_connection.py        94     94     0%   7-220
app/dependency_checker.py                 77     46    40%   42-43, 67-78, 115-127, 132-154, 170-183
app/exception_handlers.py                 79     26    67%   223-253, 255-265, 269
app/exceptions.py                         74     21    72%   109, 140, 163, 191, 214, 327, 356, 384-388, 411-415, 443, 466, 496-500
app/main.py                              140     23    84%   22-27, 53-54, 82-88, 114, 143-144, 244, 339-340, 360-362
app/middleware/__init__.py                11      0   100%
app/middleware/alerting.py               293    147    50%   121-128, 147-149, 161-218, 222-228, 256-261, 273-324, 400-414, 499-513, 562-565, 581, 585, 605-606, 618-636, 662-667, 677-704, 750-751, 761-764, 770-796, 856-858, 956-988
app/middleware/api_versioning.py          21      6    71%   49-56
app/middleware/authentication.py         115     20    83%   175-177, 233, 268, 281-309
app/middleware/cors_config.py              9      3    67%   48-70
app/middleware/csrf.py                    63     47    25%   48-52, 61, 75-82, 95-114, 127-140, 154-220
app/middleware/deprecation.py             56      7    88%   107, 115, 133-135, 146-147, 161
app/middleware/logging.py                 57      1    98%   63
app/middleware/metrics.py                209     51    76%   229-230, 242-251, 297, 301, 315-317, 333, 343, 354, 359, 369, 374, 384, 394, 404, 415, 426, 436, 446, 457, 468, 479, 489, 499, 512-515, 528-531, 544-547, 552, 557, 562, 572, 577, 582, 592, 602, 616-617
app/middleware/profiling.py               47     34    28%   41-51, 55-97
app/middleware/rate_limiting.py           94     59    37%   59, 89-104, 118-135, 147-157, 188-271
app/middleware/request_size_limit.py      49      9    82%   62-63, 114-115, 124-157
app/middleware/schema_validation.py      158    140    11%   53-60, 80-102, 112-171, 194-236, 248-274, 287-302, 318-353, 367-421, 441-443
app/middleware/tracing.py                 77     57    26%   15-22, 56-123, 128-142, 147-149, 154-155, 164-184
app/models/__init__.py                     2      0   100%
app/models/schemas.py                    693    184    73%   39-45, 51-69, 75-91, 97-114, 119-125, 158-167, 173-191, 197-213, 219-236, 340, 346, 356, 360, 364, 368, 377, 380, 385, 390, 402, 406, 415, 420, 447, 451-453, 457, 468, 472, 668-675, 681-688, 739, 748, 753, 758-761, 773, 778, 784, 796-798, 802-804, 808-810, 814-818, 822-824, 833, 837-839, 843-845, 849-851, 857-859, 863-866, 1149, 1153, 1164, 1168, 1177, 1181, 1407, 1410, 1421, 1426, 1445, 1448, 1453, 1455, 1564, 1567, 1570, 1579, 1582, 1587, 1589
app/routes/__init__.py                    10      0   100%
app/routes/api_keys.py                   112      4    96%   383-386
app/routes/auth.py                        45     17    62%   92-94, 147, 150-151, 187-193, 234-249
app/routes/export.py                      90     65    28%   52-57, 68-69, 109-166, 203-215, 266-302, 339-353
app/routes/health.py                      28      1    96%   122
app/routes/metrics.py                    158    113    28%   34-36, 42-44, 57, 75-79, 103-113, 137-147, 171-181, 205-215, 239-265, 290-449, 468-473, 492-497, 516-520, 539-543, 567-577, 596-600
app/routes/sessions.py                   174    125    28%   70-83, 104-106, 112, 157-198, 231-238, 273-280, 317-347, 375-407, 440-458, 490-508, 540-558, 590-608, 640-653, 685-703
app/routes/state.py                      146     95    35%   88-138, 141-142, 197, 206-303, 306-307, 353-363, 366-367, 411-424, 427-428, 472-489, 492-493
app/routes/tasks.py                      166     89    46%   204, 238-278, 313-360, 410-412, 449-521, 552-582, 612-639
app/routes/templates.py                  140    117    16%   39, 70-137, 168-252, 279-317, 349-422, 446-471
app/routes/users.py                      122     58    52%   95-99, 127-158, 185-204, 236-251, 287-292, 365, 413, 444-448, 488, 500-504, 536-539
app/routes/version.py                     32     10    69%   62-252, 304
app/routes/webhooks.py                    69      0   100%
app/services/__init__.py                   4      0   100%
app/services/auth_manager.py             249    154    38%   59, 122, 127, 146-151, 160, 165, 170-171, 276, 280-281, 289, 308-348, 369-417, 430-461, 485, 506-562, 584-620, 632-654
app/services/authorization.py            149     76    49%   147-163, 182-185, 199-206, 236-261, 266-315, 331, 371, 381-393, 421, 453-459, 473-484, 517-536, 584-633
app/services/business_metrics.py          89     58    35%   59-73, 82-185, 197-247, 268-323, 340-386, 402-426, 446
app/services/cache_service.py            124     78    37%   53, 73-74, 86-87, 103-106, 120-121, 137-140, 154-155, 169-170, 182-183, 197-200, 214-215, 231-232, 244-245, 262-263, 276-277, 289-293, 305-309, 323, 332-343, 347-352, 356-363, 367-371, 375-381
app/services/data_export.py              132    116    12%   32-33, 62-91, 114-165, 177-178, 190-195, 207-278, 296-315, 347-367, 392-402
app/services/error_recovery.py           152      4    97%   60, 328, 346, 373
app/services/health_check.py             103     20    81%   52-56, 63-65, 81-85, 92-94, 125-129, 160, 172, 176, 181-187, 214, 228-229
app/services/profiling_service.py        141    109    23%   56-60, 64-67, 71-94, 106-120, 124-128, 146-189, 195-234, 238-266, 270-330
app/services/rate_limiter.py              44     33    25%   50-84, 96-120
app/services/seeding_service.py          163    163     0%   7-541
app/services/session_manager.py          359     80    78%   216, 330-331, 373, 424, 447-449, 453-454, 464-465, 492-518, 533, 563-569, 619-680, 714-717, 750-753, 759-760, 806, 820-827
app/services/sharding_service.py          63     63     0%   7-223
app/services/task_executor.py            194     96    51%   45-57, 79-99, 338, 352, 373, 392-404, 429-449, 483-488, 509-544, 595-603, 606, 610-622
app/services/user_management.py          167    104    38%   47-85, 99, 113-116, 138, 166-190, 217-218, 230-233, 253-292, 304-355, 380-383, 403-405
app/services/webhook_manager.py          149     41    72%   85-86, 95, 215, 221-225, 237-267, 270-282, 295
app/tasks/__init__.py                      2      0   100%
app/tasks/experimental_tasks.py          171    111    35%   44-45, 53, 63, 93, 137-188, 213-264, 288-337, 356-403, 422-471
app/tasks/task_registry.py                27      0   100%
app/tracing.py                            50     50     0%   7-126
--------------------------------------------------------------------
TOTAL                                   6766   3185    53%
Coverage HTML written to dir htmlcov

=========================== short test summary info ============================
SKIPPED [1] tests/property/test_migration_properties.py:294: Migration tests require PostgreSQL database for ARRAY and JSONB types
SKIPPED [1] tests/property/test_migration_properties.py:388: Migration tests require PostgreSQL database for ARRAY and JSONB types
SKIPPED [1] tests/property/test_migration_properties.py:463: Migration tests require PostgreSQL database for ARRAY and JSONB types
SKIPPED [1] tests/property/test_migration_properties.py:542: Migration tests require PostgreSQL database for ARRAY and JSONB types
FAILED tests/integration/test_state_integration.py::TestStateRoutesIntegration::test_get_system_state_authenticated - assert 500 == 200
FAILED tests/integration/test_state_integration.py::TestStateRoutesIntegration::test_get_ignition_history_authenticated - assert 500 == 200
FAILED tests/integration/test_state_integration.py::TestStateRoutesIntegration::test_get_interoceptive_state_authenticated - assert 500 == 200
FAILED tests/integration/test_state_integration.py::TestStateRoutesIntegration::test_get_prediction_errors_authenticated - assert 500 == 200
FAILED tests/integration/test_state_integration.py::TestStateRoutesIntegration::test_get_somatic_markers_authenticated - assert 500 == 200
FAILED tests/property/test_auth_properties.py::test_property_6_password_hashing_verification - TypeError: AuthManager.hash_password() missing 1 required positional argume...
FAILED tests/property/test_auth_properties.py::test_property_6_password_hashing_different_password_fails - TypeError: AuthManager.hash_password() missing 1 required positional argume...
FAILED tests/property/test_auth_properties.py::test_property_6_password_hashing_deterministic_verification - TypeError: AuthManager.hash_password() missing 1 required positional argume...
FAILED tests/property/test_auth_properties.py::test_property_6_password_hashing_unique_salts - TypeError: AuthManager.hash_password() missing 1 required positional argume...
FAILED tests/property/test_auth_properties.py::test_property_6_password_hashing_long_passwords - TypeError: AuthManager.hash_password() missing 1 required positional argume...
FAILED tests/unit/test_authentication_middleware.py::TestAuthenticationMiddleware::test_blocking_verify_token - TypeError: An asyncio.Future, a coroutine or an awaitable is required
FAILED tests/unit/test_authentication_middleware.py::TestAuthenticationMiddleware::test_blocking_verify_api_key_valid - ValueError: Invalid API key
FAILED tests/unit/test_authentication_middleware.py::TestAuthenticationMiddleware::test_blocking_verify_api_key_expired - AssertionError: Regex pattern did not match.
FAILED tests/unit/test_experimental_tasks.py::TestExecuteIowaGamblingTask::test_execute_iowa_gambling_task_success - TypeError: execute_iowa_gambling_task() takes 3 positional arguments but 4 ...
FAILED tests/unit/test_experimental_tasks.py::TestExecuteIowaGamblingTask::test_execute_iowa_gambling_task_failure - TypeError: execute_iowa_gambling_task() takes 3 positional arguments but 4 ...
FAILED tests/unit/test_experimental_tasks.py::TestExecuteMaskingParadigmTask::test_execute_masking_paradigm_task_success - TypeError: execute_masking_paradigm_task() takes 3 positional arguments but...
FAILED tests/unit/test_experimental_tasks.py::TestExecuteAttentionalBlinkTask::test_execute_attentional_blink_task_success - TypeError: execute_attentional_blink_task() takes 3 positional arguments bu...
FAILED tests/unit/test_experimental_tasks.py::TestExecuteChangeBlindnessTask::test_execute_change_blindness_task_success - TypeError: execute_change_blindness_task() takes 3 positional arguments but...
FAILED tests/unit/test_experimental_tasks.py::TestExecuteBinocularRivalryTask::test_execute_binocular_rivalry_task_success - TypeError: execute_binocular_rivalry_task() takes 3 positional arguments bu...
FAILED tests/unit/test_session_manager.py::TestSimulationSession::test_simulation_session_initialization - FileNotFoundError: [Errno 2] No such file or directory: '/path/to/config.yaml'
FAILED tests/unit/test_session_manager.py::TestSimulationSession::test_can_transition_to_valid - AssertionError: assert True is False
FAILED tests/unit/test_session_manager.py::TestSimulationSession::test_start_from_created - FileNotFoundError: [Errno 2] No such file or directory: '/path/to/config.yaml'
FAILED tests/unit/test_session_manager.py::TestSimulationSession::test_reset_session - ValueError: Cannot reset session in state created
FAILED tests/unit/test_session_manager.py::TestSimulationSession::test_restore_state - AttributeError: 'AllostaticRegulator' object has no attribute 'load_state'
FAILED tests/unit/test_session_manager.py::TestSessionManager::test_create_session_basic - TypeError: Object of type MagicMock is not JSON serializable
FAILED tests/unit/test_session_manager.py::TestSessionManager::test_create_session_with_template - pydantic_core._pydantic_core.ValidationError: 1 validation error for Sessio...
FAILED tests/unit/test_session_manager.py::TestSessionManager::test_get_session_from_cache - ValueError: Invalid session ID format: test-session-123
FAILED tests/unit/test_session_manager.py::TestSessionManager::test_get_session_from_redis - ValueError: Invalid session ID format: test-session-123
FAILED tests/unit/test_session_manager.py::TestSessionManager::test_get_session_from_database - ValueError: Invalid session ID format: test-session-123
FAILED tests/unit/test_session_manager.py::TestSessionManager::test_delete_session - ValueError: Invalid session ID format: test-session-123
FAILED tests/unit/test_session_manager.py::TestSessionManager::test_update_session_state - ValueError: Invalid session ID format: test-session-123
FAILED tests/unit/test_session_manager.py::TestSessionManager::test_list_sessions - TypeError: Boolean value of this clause is not defined
FAILED tests/unit/test_webhook_manager.py::TestValidateWebhookUrl::test_validate_webhook_url_private_ip - Failed: DID NOT RAISE <class 'ValueError'>
FAILED tests/unit/test_webhook_manager.py::TestValidateWebhookUrl::test_validate_webhook_url_cloud_metadata - AssertionError: Regex pattern did not match.
FAILED tests/unit/test_webhook_manager.py::TestDeliverWebhook::test_deliver_webhook_max_attempts - TypeError: 'MagicMock' object can't be awaited
FAILED tests/unit/test_webhook_manager.py::TestDeliverWebhook::test_deliver_webhook_success - assert False
FAILED tests/unit/test_webhook_manager.py::TestDeliverWebhook::test_deliver_webhook_timeout - assert "coroutine" ...exit__ method)" == 'Timeout'
FAILED tests/unit/test_webhook_manager.py::TestWebhookManagerLifecycle::test_close - AttributeError: 'NoneType' object has no attribute 'close'
FAILED tests/unit/test_webhooks.py::TestRetryWebhookDelivery::test_retry_webhook_delivery_success - fastapi.exceptions.HTTPException: 500: An internal error occurred
============ 39 failed, 357 passed, 4 skipped, 3 warnings in 18.73s ============