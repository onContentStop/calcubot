"""
A Discord bot which properly parses and evaluates mathematical expressions.

The bot is resistant to errors and complex computations.
"""
from decimal import Decimal
from math import cos, factorial, pi, sin, sqrt, tan, log
from typing import Any, Callable, Tuple
from fractions import Fraction
from asyncio.exceptions import InvalidStateError
from discord.ext import commands
from discord.ext.commands.bot import Context
from lark import Lark, Transformer
from lark import ParseError
from lark.exceptions import UnexpectedCharacters, VisitError
from sys import float_info
from lark.tree import Tree
from timeout_decorator import (
    timeout,
    TimeoutError as TimeoutDecoratorTimeoutError,
)


class Debug(Exception):
    def __init__(self, args) -> None:
        self.args = args


class Interpreter(Transformer):
    def sum(self, args):
        if args[1] == "+":
            return Decimal(args[0]) + Decimal(args[2])
        if args[1] == "-":
            return Decimal(args[0]) - Decimal(args[2])
        raise InvalidStateError()

    def product(self, args):
        print(repr(args))
        if args[1] == "*":
            return Decimal(args[0]) * Decimal(args[2])
        if args[1] == "/":
            return Decimal(args[0]) / Decimal(args[2])
        if args[1] == "%":
            return Decimal(args[0]) % Decimal(args[2])
        raise InvalidStateError()

    def power(self, args):
        return Decimal(args[0]) ** Decimal(args[1])

    def unary(self, args):
        if args[0] == "+":
            return Decimal(args[1])
        return -Decimal(args[1])

    def function_call(self, args):
        if args[0] == "abs":
            return self.nargs(1, args[1:], "abs", abs)
        if args[0] == "sin":
            return self.nargs(1, args[1:], "sin", sin)
        if args[0] == "cos":
            return self.nargs(1, args[1:], "cos", cos)
        if args[0] == "tan":
            return self.nargs(1, args[1:], "tan", tan)
        if args[0] == "deg_to_rad":
            return self.nargs(
                1, args[1:], "deg_to_rad", lambda x: x * pi / 180
            )
        if args[0] == "rad_to_deg":
            return self.nargs(
                1, args[1:], "rad_to_deg", lambda x: x * 180 / pi
            )
        if args[0] == "sqrt":
            return self.nargs(1, args[1:], "sqrt", sqrt)
        if args[0] == "fact":
            return self.nargs(1, args[1:], "fact", factorial)
        if args[0] == "log":
            return self.nargs(2, args[1:], "log", log)
        if args[0] == "debug":
            raise Debug(args[1:])
        raise ValueError(f"unknown function {args[0]}({args[1]})")

    def nargs(self, n: int, args: Tuple[str], fn: str, f: Callable):
        if len(args) != n:
            raise ValueError(f"function {fn} takes {n} args, not {len(args)}")

        @timeout(seconds=5)
        def caller(f, args):
            return f(*args)

        try:
            return caller(f, tuple(map(float, args)))
        except TimeoutDecoratorTimeoutError:
            raise ValueError(
                f"function {fn} took too long to run and "
                + "was killed. You've been a bad boy."
            )


async def do_calc(ctx: Context, lark: Lark, args: Tuple[Any, ...]) -> None:
    """Perform the calculation."""
    try:
        parsed = lark.parse(" ".join(args))
    except ParseError as e:
        await ctx.send(f"Encountered an error while parsing: {e}")
        return
    except UnexpectedCharacters as e:
        await ctx.send(f"Unexpected characters: {e}")
        return
    try:
        if isinstance(parsed, Tree):
            res = Interpreter().transform(parsed)
        else:
            res = Decimal(parsed)
    except ValueError as e:
        await ctx.send(f"Encountered an error while evaluating: {e}")
        return
    except VisitError as e:
        if isinstance(e.orig_exc, Debug):
            await ctx.send(e.orig_exc.args[0])
        elif isinstance(e.orig_exc, TimeoutError):
            await ctx.send(
                f"Encountered an error while evaluating: {e.orig_exc}"
            )
        else:
            await ctx.send("\n".join(map(str, e.orig_exc.args)))
        return
    if res % 1 > float_info.epsilon and (1 - res % 1) > float_info.epsilon:
        await ctx.send(
            f"The answer is `{Fraction(res)}`.\nIt can also be "
            + f"written as `{float(res)}`"
        )
    else:
        await ctx.send(f"The answer is `{Fraction(res)}`")


if __name__ == "__main__":
    bot = commands.Bot(command_prefix="#")
    with open("token.txt") as f:
        token = f.read()
    with open("calc.lark") as f:
        lark = Lark(f.read())

    @bot.command(help="Calculate the value of an expression.")
    async def calc(ctx: Context, *args):
        """Calculate the value of an expression."""
        if len(args) == 0:
            await ctx.send_help("calc")
            return
        await do_calc(ctx, lark, args)

    @bot.event
    async def on_command_error(ctx: Context, error):
        if isinstance(error, commands.errors.CommandNotFound):
            await ctx.send("Hey dum dum, that's not a real command!")
        else:
            print(error)

    bot.run(token)
    print()
