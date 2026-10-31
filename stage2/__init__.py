"""
Paper III — Stage 2: the fifth conjoined check.

    { t : t in types(d) and subject_linked(t,d) }  subset-of  role_permissions[role(r)]

Stage 2a (this package, so far) builds the authoring scaffold only. The role
permission sets are the normative artifact of the paper and are authored by the
researcher, not by a model: Paper II's finding is that language models cannot
author normative policy (ACL conformance as low as 23%, self-agreement as low as
26%), so a model-authored permission set would refute the paper it belongs to.

Nothing in this package proposes, defaults, or ranks a permission decision.
"""

STAGE = "paper3-stage2"
