#  ___________________________________________________________________________
#
#  Pyomo: Python Optimization Modeling Objects
#  Copyright (c) 2008-2024
#  National Technology and Engineering Solutions of Sandia, LLC
#  Under the terms of Contract DE-NA0003525 with National Technology and
#  Engineering Solutions of Sandia, LLC, the U.S. Government retains certain
#  rights in this software.
#  This software is distributed under the 3-clause BSD License.
#  ___________________________________________________________________________

from pyomo.core.expr import numvalue, numeric_expr, boolean_value, logical_expr
from pyomo.core.expr.numvalue import (
    value,
    is_constant,
    is_fixed,
    is_variable_type,
    is_potentially_variable,
    NumericValue,
    ZeroConstant,
    native_numeric_types,
    native_types,
    polynomial_degree,
)
from pyomo.core.expr.boolean_value import BooleanValue
from pyomo.core.expr import (
    log,
    log10,
    sin,
    cos,
    tan,
    cosh,
    sinh,
    tanh,
    asin,
    acos,
    atan,
    exp,
    sqrt,
    asinh,
    acosh,
    atanh,
    ceil,
    floor,
    Expr_if,
    inequality,
    linear_expression,
    nonlinear_expression,
    land,
    lor,
    equivalent,
    exactly,
    atleast,
    atmost,
    implies,
    lnot,
    xor,
)
from pyomo.core.expr.calculus.derivatives import differentiate
from pyomo.core.expr.taylor_series import taylor_series_expansion

from pyomo.core.kernel import (
    base,
    homogeneous_container,
    heterogeneous_container,
    variable,
    constraint,
    matrix_constraint,
    parameter,
    expression,
    objective,
    sos,
    suffix,
    block,
    piecewise_library,
    set_types,
)

# TODO: These are included for backwards compatibility.  Accessing them
# will result in a deprecation warning
from pyomo.common.dependencies import attempt_import

component_map = attempt_import('pyomo.core.kernel.component_map')[0]
component_set = attempt_import('pyomo.core.kernel.component_set')[0]
