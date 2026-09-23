*** Settings ***
Documentation     Demonstrates polling an asynchronous job with exponential backoff.
Resource          ../../resources/api_keywords.resource
Suite Setup       Suite Setup For API Tests
Suite Teardown    Suite Teardown For API Tests
Test Tags         api    async


*** Test Cases ***
Async Job Completes And Returns A Result
    ${final}=    Start Job And Wait Until Done    timeout=10
    Should Be Equal    ${final}[status]    done
    Should Be Equal As Integers    ${final}[result][records]    42

Polling Times Out When Condition Is Never Met
    ${job}=    Api.Send Request    POST    /jobs    expected_status=202
    Run Keyword And Expect Error    *Condition not met*
    ...    Api.Wait Until Json Field Equals    /jobs/${job}[body][id]    status    never
    ...    timeout=1    interval=0.1

Unknown Job Is Reported As Not Found
    Request Should Fail With Category    GET    /jobs/9999    NOT_FOUND
