#  ___________________________________________________________________________
#
#  Pyomo: Python Optimization Modeling Objects
#  Copyright (c) 2008-2022 National Technology and Engineering Solutions of Sandia, LLC
#  Under the terms of Contract DE-NA0003525 with National Technology and 
#  Engineering Solutions of Sandia, LLC, the U.S. Government retains certain 
#  rights in this software.
#  This software is distributed under the 3-clause BSD License.
#  ___________________________________________________________________________

from pyomo.environ import AbstractModel, Var, Constraint, value

model = AbstractModel()
model.X = Var()

def c_rule(m):
    if m.X >= 10.0:
        pass
    if value(m.X) >= 10.0:
        pass
    return m.X >= 10.0

model.C = Constraint(rule=c_rule)
