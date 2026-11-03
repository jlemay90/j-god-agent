"""Allow a small pure-Python scoring language; not general shell/Python access."""
import ast

BUILTINS={'str','int','float','bool','len','min','max','sum','sorted','set','list','dict','tuple','enumerate','range','abs','round','any','all','zip'}
METHODS={'lower','casefold','split','join','get','items','values','keys','startswith','endswith','strip','replace','find','count','append','extend','add','intersection','union','setdefault','sub','findall','search','match','fullmatch','escape','isdigit','isalpha','isalnum'}
FORBIDDEN=(ast.ClassDef,ast.AsyncFunctionDef,ast.Await,ast.Yield,ast.YieldFrom,ast.With,ast.AsyncWith,ast.Global,ast.Nonlocal,ast.While,ast.Try,ast.Raise,ast.Delete,ast.Lambda,ast.ImportFrom,ast.NamedExpr)


def validate(source):
    if len(source)>16000:
        raise ValueError('Source too large')
    tree=ast.parse(source)
    functions={n.name for n in tree.body if isinstance(n,ast.FunctionDef)}
    if functions!={'score'}:
        raise ValueError('Exactly one function named score is required')
    for node in tree.body:
        if not isinstance(node,(ast.Import,ast.FunctionDef)):
            raise ValueError('Only imports and function definition at module level')
    fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef))
    if fn.decorator_list or fn.returns or fn.args.defaults or fn.args.kw_defaults or fn.args.vararg or fn.args.kwarg or len(fn.args.args)!=2:
        raise ValueError('score must take exactly memory, query; no decorators, annotations or defaults')
    if [a.arg for a in fn.args.args]!=['memory','query'] or any(a.annotation for a in fn.args.args):
        raise ValueError('Unsupported score signature')
    for node in ast.walk(tree):
        if isinstance(node,FORBIDDEN):
            raise ValueError('Unsupported language construct')
        if isinstance(node,ast.Import):
            if any(a.name not in {'re','math'} or a.asname for a in node.names):
                raise ValueError('Only re/math imports allowed')
        if isinstance(node,ast.Name) and node.id.startswith('_'):
            raise ValueError('Private identifiers forbidden')
        if isinstance(node,ast.Attribute) and (node.attr.startswith('_') or node.attr not in METHODS):
            raise ValueError('Unsupported attribute/method')
        if isinstance(node,ast.Call):
            if isinstance(node.func,ast.Name):
                if node.func.id not in BUILTINS:
                    raise ValueError('Unsupported function call')
            elif not isinstance(node.func,ast.Attribute):
                raise ValueError('Indirect calls forbidden')
    return tree
