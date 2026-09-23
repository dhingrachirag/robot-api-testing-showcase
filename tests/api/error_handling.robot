*** Settings ***
Documentation     Every failure is classified into a category, which makes
...               reports much faster to triage than raw status codes.
Resource          ../../resources/api_keywords.resource
Suite Setup       Suite Setup For API Tests
Suite Teardown    Suite Teardown For API Tests
Test Template     Status Code Should Be Classified As
Test Tags         api    errors


*** Test Cases ***    STATUS    CATEGORY
Unauthorized          401       AUTH_ERROR
Forbidden             403       AUTH_ERROR
Not Found             404       NOT_FOUND
Bad Request           400       VALIDATION_ERROR
Rate Limited          429       RATE_LIMITED
Conflict              409       CLIENT_ERROR
Internal Error        500       SERVER_ERROR
Service Unavailable   503       SERVER_ERROR


*** Keywords ***
Status Code Should Be Classified As
    [Arguments]    ${status}    ${category}
    ${resp}=    Request Should Fail With Category    GET    /status/${status}    ${category}
    Should Be Equal As Integers    ${resp}[status]    ${status}
