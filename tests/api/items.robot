*** Settings ***
Documentation     CRUD tests for the /items resource.
Resource          ../../resources/api_keywords.resource
Suite Setup       Suite Setup For API Tests
Suite Teardown    Suite Teardown For API Tests
Test Tags         api    items


*** Test Cases ***
List Items Returns Seed Data
    ${resp}=    Api.Send Request    GET    /items    expected_status=200
    ${count}=    Get Length    ${resp}[body]
    Should Be True    ${count} >= 2
    ${first_name}=    Api.Get Json Value    ${resp}[body]    [0].name
    Should Be Equal    ${first_name}    alpha

Nested Values Can Be Read By Path
    ${item}=    Get Item    1
    ${tag}=    Api.Get Json Value    ${item}    tags[1]
    Should Be Equal    ${tag}    first

Create, Read And Delete An Item
    [Tags]    smoke
    ${created}=    Create Item    gamma    new    demo
    Should Be Equal    ${created}[name]    gamma
    Lists Should Be Equal    ${created}[tags]    ${{["new", "demo"]}}
    ${fetched}=    Get Item    ${created}[id]
    Dictionaries Should Be Equal    ${created}    ${fetched}
    Delete Item    ${created}[id]
    Item Should Not Exist    ${created}[id]

Creating An Item Without A Name Is Rejected
    ${payload}=    Create Dictionary    tags=${{["x"]}}
    ${resp}=    Request Should Fail With Category    POST    /items    VALIDATION_ERROR    json=${payload}
    Should Be Equal As Integers    ${resp}[status]    422

All Requests Reuse One HTTP Session
    Api.Session Should Have Been Reused
