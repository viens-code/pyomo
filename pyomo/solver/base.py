#  ___________________________________________________________________________
#
#  Pyomo: Python Optimization Modeling Objects
#  Copyright (c) 2008-2022
#  National Technology and Engineering Solutions of Sandia, LLC
#  Under the terms of Contract DE-NA0003525 with National Technology and
#  Engineering Solutions of Sandia, LLC, the U.S. Government retains certain
#  rights in this software.
#  This software is distributed under the 3-clause BSD License.
#  ___________________________________________________________________________

import abc
import enum
from typing import Sequence, Dict, Optional, Mapping, NoReturn, List, Tuple
import os

from pyomo.core.base.constraint import _GeneralConstraintData
from pyomo.core.base.var import _GeneralVarData
from pyomo.core.base.param import _ParamData
from pyomo.core.base.block import _BlockData
from pyomo.core.base.objective import _GeneralObjectiveData
from pyomo.common.timing import HierarchicalTimer
from pyomo.common.errors import ApplicationError
from pyomo.opt.results.results_ import SolverResults as LegacySolverResults
from pyomo.opt.results.solution import Solution as LegacySolution
from pyomo.core.kernel.objective import minimize
from pyomo.core.base import SymbolMap
from pyomo.core.staleflag import StaleFlagManager
from pyomo.solver.config import UpdateConfig
from pyomo.solver.util import get_objective
from pyomo.solver.results import (
    Results,
    legacy_solver_status_map,
    legacy_termination_condition_map,
    legacy_solution_status_map,
)


class SolverBase(abc.ABC):
    """
    Base class upon which direct solver interfaces can be built.

    This base class contains the required methods for all direct solvers:
        - available: Determines whether the solver is able to be run, combining
        both whether it can be found on the system and if the license is valid.
        - config: The configuration method for solver objects.
        - solve: The main method of every solver
        - version: The version of the solver
        - is_persistent: Set to false for all direct solvers.
    """

    #
    # Support "with" statements. Forgetting to call deactivate
    # on Plugins is a common source of memory leaks
    #
    def __enter__(self):
        return self

    def __exit__(self, t, v, traceback):
        """Exit statement - enables `with` statements."""

    class Availability(enum.IntEnum):
        """
        Class to capture different statuses in which a solver can exist in
        order to record its availability for use.
        """

        FullLicense = 2
        LimitedLicense = 1
        NotFound = 0
        BadVersion = -1
        BadLicense = -2
        NeedsCompiledExtension = -3

        def __bool__(self):
            return self._value_ > 0

        def __format__(self, format_spec):
            # We want general formatting of this Enum to return the
            # formatted string value and not the int (which is the
            # default implementation from IntEnum)
            return format(self.name, format_spec)

        def __str__(self):
            # Note: Python 3.11 changed the core enums so that the
            # "mixin" type for standard enums overrides the behavior
            # specified in __format__.  We will override str() here to
            # preserve the previous behavior
            return self.name

    @abc.abstractmethod
    def solve(
        self, model: _BlockData, timer: HierarchicalTimer = None, **kwargs
    ) -> Results:
        """
        Solve a Pyomo model.

        Parameters
        ----------
        model: _BlockData
            The Pyomo model to be solved
        timer: HierarchicalTimer
            An option timer for reporting timing
        **kwargs
            Additional keyword arguments (including solver_options - passthrough
            options; delivered directly to the solver (with no validation))

        Returns
        -------
        results: Results
            A results object
        """

    @abc.abstractmethod
    def available(self):
        """Test if the solver is available on this system.

        Nominally, this will return True if the solver interface is
        valid and can be used to solve problems and False if it cannot.

        Note that for licensed solvers there are a number of "levels" of
        available: depending on the license, the solver may be available
        with limitations on problem size or runtime (e.g., 'demo'
        vs. 'community' vs. 'full').  In these cases, the solver may
        return a subclass of enum.IntEnum, with members that resolve to
        True if the solver is available (possibly with limitations).
        The Enum may also have multiple members that all resolve to
        False indicating the reason why the interface is not available
        (not found, bad license, unsupported version, etc).

        Returns
        -------
        available: Solver.Availability
            An enum that indicates "how available" the solver is.
            Note that the enum can be cast to bool, which will
            be True if the solver is runable at all and False
            otherwise.
        """

    @abc.abstractmethod
    def version(self) -> Tuple:
        """
        Returns
        -------
        version: tuple
            A tuple representing the version
        """

    @property
    @abc.abstractmethod
    def config(self):
        """
        An object for configuring solve options.

        Returns
        -------
        SolverConfig
            An object for configuring pyomo solve options such as the time limit.
            These options are mostly independent of the solver.
        """

    def is_persistent(self):
        """
        Returns
        -------
        is_persistent: bool
            True if the solver is a persistent solver.
        """
        return False


class PersistentSolverBase(SolverBase):
    """
    Base class upon which persistent solvers can be built. This inherits the
    methods from the direct solver base and adds those methods that are necessary
    for persistent solvers.

    Example usage can be seen in solvers within APPSI.
    """

    def is_persistent(self):
        """
        Returns
        -------
        is_persistent: bool
            True if the solver is a persistent solver.
        """
        return True

    def load_vars(
        self, vars_to_load: Optional[Sequence[_GeneralVarData]] = None
    ) -> NoReturn:
        """
        Load the solution of the primal variables into the value attribute of the variables.

        Parameters
        ----------
        vars_to_load: list
            A list of the variables whose solution should be loaded. If vars_to_load is None, then the solution
            to all primal variables will be loaded.
        """
        for v, val in self.get_primals(vars_to_load=vars_to_load).items():
            v.set_value(val, skip_validation=True)
        StaleFlagManager.mark_all_as_stale(delayed=True)

    @abc.abstractmethod
    def get_primals(
        self, vars_to_load: Optional[Sequence[_GeneralVarData]] = None
    ) -> Mapping[_GeneralVarData, float]:
        """
        Get mapping of variables to primals.

        Parameters
        ----------
        vars_to_load : Optional[Sequence[_GeneralVarData]], optional
            Which vars to be populated into the map. The default is None.

        Returns
        -------
        Mapping[_GeneralVarData, float]
            A map of variables to primals.
        """
        raise NotImplementedError(
            '{0} does not support the get_primals method'.format(type(self))
        )

    def get_duals(
        self, cons_to_load: Optional[Sequence[_GeneralConstraintData]] = None
    ) -> Dict[_GeneralConstraintData, float]:
        """
        Declare sign convention in docstring here.

        Parameters
        ----------
        cons_to_load: list
            A list of the constraints whose duals should be loaded. If cons_to_load is None, then the duals for all
            constraints will be loaded.

        Returns
        -------
        duals: dict
            Maps constraints to dual values
        """
        raise NotImplementedError(
            '{0} does not support the get_duals method'.format(type(self))
        )

    def get_slacks(
        self, cons_to_load: Optional[Sequence[_GeneralConstraintData]] = None
    ) -> Dict[_GeneralConstraintData, float]:
        """
        Parameters
        ----------
        cons_to_load: list
            A list of the constraints whose slacks should be loaded. If cons_to_load is None, then the slacks for all
            constraints will be loaded.

        Returns
        -------
        slacks: dict
            Maps constraints to slack values
        """
        raise NotImplementedError(
            '{0} does not support the get_slacks method'.format(type(self))
        )

    def get_reduced_costs(
        self, vars_to_load: Optional[Sequence[_GeneralVarData]] = None
    ) -> Mapping[_GeneralVarData, float]:
        """
        Parameters
        ----------
        vars_to_load: list
            A list of the variables whose reduced cost should be loaded. If vars_to_load is None, then all reduced costs
            will be loaded.

        Returns
        -------
        reduced_costs: ComponentMap
            Maps variable to reduced cost
        """
        raise NotImplementedError(
            '{0} does not support the get_reduced_costs method'.format(type(self))
        )

    @property
    @abc.abstractmethod
    def update_config(self) -> UpdateConfig:
        """
        Updates the solver config
        """

    @abc.abstractmethod
    def set_instance(self, model):
        """
        Set an instance of the model
        """

    @abc.abstractmethod
    def add_variables(self, variables: List[_GeneralVarData]):
        """
        Add variables to the model
        """

    @abc.abstractmethod
    def add_params(self, params: List[_ParamData]):
        """
        Add parameters to the model
        """

    @abc.abstractmethod
    def add_constraints(self, cons: List[_GeneralConstraintData]):
        """
        Add constraints to the model
        """

    @abc.abstractmethod
    def add_block(self, block: _BlockData):
        """
        Add a block to the model
        """

    @abc.abstractmethod
    def remove_variables(self, variables: List[_GeneralVarData]):
        """
        Remove variables from the model
        """

    @abc.abstractmethod
    def remove_params(self, params: List[_ParamData]):
        """
        Remove parameters from the model
        """

    @abc.abstractmethod
    def remove_constraints(self, cons: List[_GeneralConstraintData]):
        """
        Remove constraints from the model
        """

    @abc.abstractmethod
    def remove_block(self, block: _BlockData):
        """
        Remove a block from the model
        """

    @abc.abstractmethod
    def set_objective(self, obj: _GeneralObjectiveData):
        """
        Set current objective for the model
        """

    @abc.abstractmethod
    def update_variables(self, variables: List[_GeneralVarData]):
        """
        Update variables on the model
        """

    @abc.abstractmethod
    def update_params(self):
        """
        Update parameters on the model
        """


class LegacySolverInterface:
    """
    Class to map the new solver interface features into the legacy solver
    interface. Necessary for backwards compatibility.
    """

    def set_config(self, config):
        # TODO: Make a mapping from new config -> old config
        pass

    def solve(
        self,
        model: _BlockData,
        tee: bool = False,
        load_solutions: bool = True,
        logfile: Optional[str] = None,
        solnfile: Optional[str] = None,
        timelimit: Optional[float] = None,
        report_timing: bool = False,
        solver_io: Optional[str] = None,
        suffixes: Optional[Sequence] = None,
        options: Optional[Dict] = None,
        keepfiles: bool = False,
        symbolic_solver_labels: bool = False,
    ):
        """
        Solve method: maps new solve method style to backwards compatible version.

        Returns
        -------
        legacy_results
            Legacy results object

        """
        original_config = self.config
        self.config = self.config()
        self.config.tee = tee
        self.config.load_solution = load_solutions
        self.config.symbolic_solver_labels = symbolic_solver_labels
        self.config.time_limit = timelimit
        self.config.report_timing = report_timing
        if solver_io is not None:
            raise NotImplementedError('Still working on this')
        if suffixes is not None:
            raise NotImplementedError('Still working on this')
        if logfile is not None:
            raise NotImplementedError('Still working on this')
        if 'keepfiles' in self.config:
            self.config.keepfiles = keepfiles
        if solnfile is not None:
            if 'filename' in self.config:
                filename = os.path.splitext(solnfile)[0]
                self.config.filename = filename
        original_options = self.options
        if options is not None:
            self.options = options

        results: Results = super().solve(model)

        legacy_results = LegacySolverResults()
        legacy_soln = LegacySolution()
        legacy_results.solver.status = legacy_solver_status_map[
            results.termination_condition
        ]
        legacy_results.solver.termination_condition = legacy_termination_condition_map[
            results.termination_condition
        ]
        legacy_soln.status = legacy_solution_status_map[results.solution_status]
        legacy_results.solver.termination_message = str(results.termination_condition)

        obj = get_objective(model)
        if len(list(obj)) > 0:
            legacy_results.problem.sense = obj.sense

            if obj.sense == minimize:
                legacy_results.problem.lower_bound = results.objective_bound
                legacy_results.problem.upper_bound = results.incumbent_objective
            else:
                legacy_results.problem.upper_bound = results.objective_bound
                legacy_results.problem.lower_bound = results.incumbent_objective
        if (
            results.incumbent_objective is not None
            and results.objective_bound is not None
        ):
            legacy_soln.gap = abs(results.incumbent_objective - results.objective_bound)
        else:
            legacy_soln.gap = None

        symbol_map = SymbolMap()
        symbol_map.byObject = dict(symbol_map.byObject)
        symbol_map.bySymbol = dict(symbol_map.bySymbol)
        symbol_map.aliases = dict(symbol_map.aliases)
        symbol_map.default_labeler = symbol_map.default_labeler
        model.solutions.add_symbol_map(symbol_map)
        legacy_results._smap_id = id(symbol_map)

        delete_legacy_soln = True
        if load_solutions:
            if hasattr(model, 'dual') and model.dual.import_enabled():
                for c, val in results.solution_loader.get_duals().items():
                    model.dual[c] = val
            if hasattr(model, 'slack') and model.slack.import_enabled():
                for c, val in results.solution_loader.get_slacks().items():
                    model.slack[c] = val
            if hasattr(model, 'rc') and model.rc.import_enabled():
                for v, val in results.solution_loader.get_reduced_costs().items():
                    model.rc[v] = val
        elif results.incumbent_objective is not None:
            delete_legacy_soln = False
            for v, val in results.solution_loader.get_primals().items():
                legacy_soln.variable[symbol_map.getSymbol(v)] = {'Value': val}
            if hasattr(model, 'dual') and model.dual.import_enabled():
                for c, val in results.solution_loader.get_duals().items():
                    legacy_soln.constraint[symbol_map.getSymbol(c)] = {'Dual': val}
            if hasattr(model, 'slack') and model.slack.import_enabled():
                for c, val in results.solution_loader.get_slacks().items():
                    symbol = symbol_map.getSymbol(c)
                    if symbol in legacy_soln.constraint:
                        legacy_soln.constraint[symbol]['Slack'] = val
            if hasattr(model, 'rc') and model.rc.import_enabled():
                for v, val in results.solution_loader.get_reduced_costs().items():
                    legacy_soln.variable['Rc'] = val

        legacy_results.solution.insert(legacy_soln)
        if delete_legacy_soln:
            legacy_results.solution.delete(0)

        self.config = original_config
        self.options = original_options

        return legacy_results

    def available(self, exception_flag=True):
        """
        Returns a bool determining whether the requested solver is available
        on the system.
        """
        ans = super().available()
        if exception_flag and not ans:
            raise ApplicationError(f'Solver {self.__class__} is not available ({ans}).')
        return bool(ans)

    def license_is_valid(self) -> bool:
        """Test if the solver license is valid on this system.

        Note that this method is included for compatibility with the
        legacy SolverFactory interface.  Unlicensed or open source
        solvers will return True by definition.  Licensed solvers will
        return True if a valid license is found.

        Returns
        -------
        available: bool
            True if the solver license is valid. Otherwise, False.

        """
        return bool(self.available())

    @property
    def options(self):
        """
        Read the options for the dictated solver.

        NOTE: Only the set of solvers for which the LegacySolverInterface is compatible
        are accounted for within this property.
        Not all solvers are currently covered by this backwards compatibility
        class.
        """
        for solver_name in ['gurobi', 'ipopt', 'cplex', 'cbc', 'highs']:
            if hasattr(self, solver_name + '_options'):
                return getattr(self, solver_name + '_options')
        raise NotImplementedError('Could not find the correct options')

    @options.setter
    def options(self, val):
        """
        Set the options for the dictated solver.
        """
        found = False
        for solver_name in ['gurobi', 'ipopt', 'cplex', 'cbc', 'highs']:
            if hasattr(self, solver_name + '_options'):
                setattr(self, solver_name + '_options', val)
                found = True
        if not found:
            raise NotImplementedError('Could not find the correct options')

    def __enter__(self):
        return self

    def __exit__(self, t, v, traceback):
        pass
