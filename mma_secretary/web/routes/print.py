from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from mma_secretary.services.documents import (
    brackets_html,
    certificates,
    corner_list,
    full_report,
    medalists_html,
    pair_list,
    personal_results,
    protocol_mandate,
    protocol_weigh_in,
    scorecards,
    team_protocol,
)
from mma_secretary.web.deps import svc

router = APIRouter()


def _html(fn):
    return HTMLResponse(
        fn(svc),
        headers={"Cache-Control": "no-store", "Content-Type": "text/html; charset=utf-8"},
    )


@router.get("/print/weigh-in")
def p1():
    return _html(protocol_weigh_in)


@router.get("/print/mandate")
def p2():
    return _html(protocol_mandate)


@router.get("/print/pairs")
def p3():
    return _html(pair_list)


@router.get("/print/corners")
def p4():
    return _html(corner_list)


@router.get("/print/brackets")
def p5():
    return _html(brackets_html)


@router.get("/print/personal")
def p6():
    return _html(personal_results)


@router.get("/print/scorecards")
def p7():
    return _html(scorecards)


@router.get("/print/teams")
def p8():
    return _html(team_protocol)


@router.get("/print/medals")
def p9():
    return _html(medalists_html)


@router.get("/print/certificates")
def p10():
    return _html(certificates)


@router.get("/print/report")
def p11():
    return _html(full_report)
