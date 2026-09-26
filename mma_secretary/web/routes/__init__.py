from mma_secretary.web.routes.catalog import router as catalog
from mma_secretary.web.routes.competition import router as competition
from mma_secretary.web.routes.pages import router as pages
from mma_secretary.web.routes.participants import router as participants
from mma_secretary.web.routes.print import router as print_docs
from mma_secretary.web.routes.reports import router as reports
from mma_secretary.web.routes.system import router as system

routers = [pages, catalog, participants, competition, reports, system, print_docs]
