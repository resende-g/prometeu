from prometeu.document.contracts import ConversionRequest, ConversionResult, Diagnostic, Severity


class ConversionPipeline:
    def run(self, request: ConversionRequest) -> ConversionResult:
        return ConversionResult(
            success=False,
            exit_code=1,
            diagnostics=(
                Diagnostic("NOT_IMPLEMENTED", "Conversão ainda não implementada.", Severity.ERROR),
            ),
        )
