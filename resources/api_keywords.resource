*** Settings ***
Documentation     Reusable, composable keywords built on top of ApiLibrary.
...               Tests read like specifications; the HTTP details live here.
Library           Collections
Library           libraries.ApiLibrary    WITH NAME    Api


*** Keywords ***
Suite Setup For API Tests
    Api.Start Mock Server
    ${health}=    Api.Send Request    GET    /health    expected_status=200
    Should Be Equal    ${health}[body][status]    ok

Suite Teardown For API Tests
    Api.Stop Mock Server

Create Item
    [Arguments]    ${name}    @{tags}
    ${payload}=    Create Dictionary    name=${name}    tags=${tags}
    ${resp}=    Api.Send Request    POST    /items    json=${payload}    expected_status=201
    RETURN    ${resp}[body]

Get Item
    [Arguments]    ${item_id}
    ${resp}=    Api.Send Request    GET    /items/${item_id}    expected_status=200
    RETURN    ${resp}[body]

Delete Item
    [Arguments]    ${item_id}
    Api.Send Request    DELETE    /items/${item_id}    expected_status=204

Item Should Not Exist
    [Arguments]    ${item_id}
    Request Should Fail With Category    GET    /items/${item_id}    NOT_FOUND

Request Should Fail With Category
    [Documentation]    Assert that a request fails in a specific, expected way.
    [Arguments]    ${method}    ${path}    ${category}    ${json}=${None}    ${timeout}=${None}
    ${resp}=    Api.Send Request    ${method}    ${path}    json=${json}    timeout=${timeout}
    Should Be Equal    ${resp}[category]    ${category}
    ...    msg=Expected ${category} but got ${resp}[category] (status ${resp}[status])
    RETURN    ${resp}

Start Job And Wait Until Done
    [Arguments]    ${timeout}=10
    ${job}=    Api.Send Request    POST    /jobs    expected_status=202
    ${final}=    Api.Wait Until Json Field Equals    /jobs/${job}[body][id]    status    done
    ...    timeout=${timeout}    fail_values=failed,cancelled
    RETURN    ${final}
