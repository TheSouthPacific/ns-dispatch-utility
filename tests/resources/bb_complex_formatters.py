from nsdu import BBCode


@BBCode.register('complex')
class Complex():
    def format(self, tag_name, value, options, parent, context):
        return "[simple1]{}[/simple1]".format(value)


@BBCode.register('complexctx', render_embedded=False)
class ComplexCtx():
    def format(self, tag_name, value, options, parent, context):
        return "[complexctxr={}]{}[/complexctxr]".format(context['example']['foo'], value)


@BBCode.register('complexopt')
class ComplexOpt():
    def format(self, tag_name, value, options, parent, context):
        return "[complexoptr={}]{}[/complexoptr]".format(options['opt'], value)