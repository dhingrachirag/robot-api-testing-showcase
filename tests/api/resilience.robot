*** Settings ***
Documentation     Timeouts and retry behaviour.
Resource          ../../resources/api_keywords.resource
Suite Setup       Suite Setup For API Tests
Suite Teardown    Suite Teardown For API Tests
Test Tags         api    resilience


*** Test Cases ***
Slow Response Is Classified As Timeout
    Request Should Fail With Category    GET    /slow?seconds=1    TIMEOUT    timeout=0.3

Retryable Errors Are Retried
    ${resp}=    Api.Send Request    GET    /status/503    retries=2
    Should Be Equal    ${resp}[category]    SERVER_ERROR
    Should Be Equal As Integers    ${resp}[attempts]    3

Non Retryable Errors Fail Fast
    ${resp}=    Api.Send Request    GET    /status/404    retries=2
    Should Be Equal As Integers    ${resp}[attempts]    1
