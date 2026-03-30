# DocMCP Test Report

**Report Generated:** {{date}}
**Test Suite Version:** {{version}}
**Environment:** {{environment}}

---

## Executive Summary

| Metric | Value |
|--------|-------|
| **Total Tests** | {{total_tests}} |
| **Passed** | {{passed}} ✓ |
| **Failed** | {{failed}} ✗ |
| **Skipped** | {{skipped}} - |
| **Errors** | {{errors}} ! |
| **Success Rate** | {{success_rate}}% |
| **Total Duration** | {{total_duration}} |

### Test Status Overview

```
{{status_chart}}
```

---

## Test Categories

### 1. Document Processing Tests

| Test | Status | Duration | Notes |
|------|--------|----------|-------|
| Document Format Detection | {{doc_format_status}} | {{doc_format_duration}} | {{doc_format_notes}} |
| Document Creation | {{doc_create_status}} | {{doc_create_duration}} | {{doc_create_notes}} |
| Document Checksum | {{doc_checksum_status}} | {{doc_checksum_duration}} | {{doc_checksum_notes}} |
| Content Extraction | {{doc_extract_status}} | {{doc_extract_duration}} | {{doc_extract_notes}} |
| Sample Files Loading | {{doc_sample_status}} | {{doc_sample_duration}} | {{doc_sample_notes}} |

**Coverage:** {{doc_coverage}}%

### 2. MCP Protocol Tests

| Test | Status | Duration | Notes |
|------|--------|----------|-------|
| Message Creation | {{mcp_msg_status}} | {{mcp_msg_duration}} | {{mcp_msg_notes}} |
| Message Serialization | {{mcp_ser_status}} | {{mcp_ser_duration}} | {{mcp_ser_notes}} |
| Error Handling | {{mcp_err_status}} | {{mcp_err_duration}} | {{mcp_err_notes}} |
| Server Functionality | {{mcp_srv_status}} | {{mcp_srv_duration}} | {{mcp_srv_notes}} |
| Connection Management | {{mcp_conn_status}} | {{mcp_conn_duration}} | {{mcp_conn_notes}} |

**Coverage:** {{mcp_coverage}}%

### 3. Skills System Tests

| Test | Status | Duration | Notes |
|------|--------|----------|-------|
| Skill Registration | {{skill_reg_status}} | {{skill_reg_duration}} | {{skill_reg_notes}} |
| Skill Execution | {{skill_exec_status}} | {{skill_exec_duration}} | {{skill_exec_notes}} |
| Skill Chain | {{skill_chain_status}} | {{skill_chain_duration}} | {{skill_chain_notes}} |
| Skill Parallel | {{skill_para_status}} | {{skill_para_duration}} | {{skill_para_notes}} |
| Skill Search | {{skill_search_status}} | {{skill_search_duration}} | {{skill_search_notes}} |

**Coverage:** {{skill_coverage}}%

### 4. Security Tests

| Test | Status | Duration | Notes |
|------|--------|----------|-------|
| Password Validation | {{sec_pwd_val_status}} | {{sec_pwd_val_duration}} | {{sec_pwd_val_notes}} |
| Password Hashing | {{sec_pwd_hash_status}} | {{sec_pwd_hash_duration}} | {{sec_pwd_hash_notes}} |
| User Authentication | {{sec_auth_status}} | {{sec_auth_duration}} | {{sec_auth_notes}} |
| Role Permissions | {{sec_role_status}} | {{sec_role_duration}} | {{sec_role_notes}} |
| Token Management | {{sec_token_status}} | {{sec_token_duration}} | {{sec_token_notes}} |
| Sandbox Execution | {{sec_sandbox_status}} | {{sec_sandbox_duration}} | {{sec_sandbox_notes}} |
| Resource Access Control | {{sec_rac_status}} | {{sec_rac_duration}} | {{sec_rac_notes}} |

**Coverage:** {{sec_coverage}}%

### 5. Performance Tests

| Test | Status | Duration | Notes |
|------|--------|----------|-------|
| Metrics Collection | {{perf_metric_status}} | {{perf_metric_duration}} | {{perf_metric_notes}} |
| Health Checks | {{perf_health_status}} | {{perf_health_duration}} | {{perf_health_notes}} |
| Alert Management | {{perf_alert_status}} | {{perf_alert_duration}} | {{perf_alert_notes}} |
| Cache Functionality | {{perf_cache_status}} | {{perf_cache_duration}} | {{perf_cache_notes}} |
| Rate Limiting | {{perf_rate_status}} | {{perf_rate_duration}} | {{perf_rate_notes}} |
| Worker Pool | {{perf_pool_status}} | {{perf_pool_duration}} | {{perf_pool_notes}} |

**Coverage:** {{perf_coverage}}%

---

## Detailed Results

### Failed Tests

{{#failed_tests}}
#### {{name}}

- **Status:** {{status}}
- **Duration:** {{duration}}
- **Error:** {{error}}
- **Stack Trace:**
```
{{stack_trace}}
```

{{/failed_tests}}

{{^failed_tests}}
*No failed tests*
{{/failed_tests}}

### Slow Tests (> 1s)

{{#slow_tests}}
- {{name}}: {{duration}}
{{/slow_tests}}

{{^slow_tests}}
*No slow tests*
{{/slow_tests}}

---

## Code Coverage

### Overall Coverage

| Metric | Percentage |
|--------|------------|
| **Lines** | {{coverage_lines}}% |
| **Branches** | {{coverage_branches}}% |
| **Functions** | {{coverage_functions}}% |

### Coverage by Module

| Module | Lines | Branches | Functions |
|--------|-------|----------|-----------|
| docmcp.core | {{core_lines}}% | {{core_branches}}% | {{core_functions}}% |
| docmcp.mcp | {{mcp_lines}}% | {{mcp_branches}}% | {{mcp_functions}}% |
| docmcp.skills | {{skills_lines}}% | {{skills_branches}}% | {{skills_functions}}% |
| docmcp.security | {{sec_lines}}% | {{sec_branches}}% | {{sec_functions}}% |
| docmcp.performance | {{perf_lines}}% | {{perf_branches}}% | {{perf_functions}}% |

### Uncovered Code

{{#uncovered}}
- {{file}}: lines {{lines}}
{{/uncovered}}

---

## Performance Metrics

### Test Execution Time

```
{{execution_time_chart}}
```

### Resource Usage

| Resource | Average | Peak |
|----------|---------|------|
| CPU Usage | {{avg_cpu}}% | {{peak_cpu}}% |
| Memory Usage | {{avg_memory}}MB | {{peak_memory}}MB |
| Disk I/O | {{avg_disk_io}} | {{peak_disk_io}} |

---

## Recommendations

{{#recommendations}}
### {{priority}}: {{title}}

{{description}}

{{/recommendations}}

{{^recommendations}}
*No recommendations at this time*
{{/recommendations}}

---

## Appendix

### Test Environment

```
Python Version: {{python_version}}
Operating System: {{os}}
CPU Count: {{cpu_count}}
Memory: {{total_memory}}
```

### Installed Dependencies

```
{{dependencies}}
```

### Test Configuration

```yaml
{{test_config}}
```

---

## Sign-off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Test Engineer | {{test_engineer}} | {{date}} | ___________ |
| QA Lead | {{qa_lead}} | {{date}} | ___________ |
| Development Lead | {{dev_lead}} | {{date}} | ___________ |

---

*This report was automatically generated by DocMCP Test Suite v{{version}}*
