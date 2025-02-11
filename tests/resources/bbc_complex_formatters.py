from nsdu import BBCode, ComplexFormatter


@BBCode.register("c1")
class Complex(ComplexFormatter):
    def format(self, tag_name, value, options, parent, context) -> str:
        return f"[cr1]{value}[/cr1]"


@BBCode.register("c2", render_embedded=False)
class ComplexCtx(ComplexFormatter):
    def format(self, tag_name, value, options, parent, context) -> str:
        return f'[cr2]ctx={context.get("foo", "")} {value}[/cr2]'


@BBCode.register("c3")
class ComplexOpt(ComplexFormatter):
    def format(self, tag_name, value, options, parent, context) -> str:
        return f'[cr3]opt={options.get("foo", "")} {value}[/cr3]'
