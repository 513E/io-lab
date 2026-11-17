"""Read a table, explain a coefficient, and compare economic structure.

Missing totals remain missing. No quiz, arbitrary matrix editor or code runner.
"""
import numpy as np


def scalar(x):
    return None if x is None else float(x)


def share(a, b):
    return float(a / b * 100) if a is not None and b is not None and b != 0 else None


class CourseMixin:
    def economy(self, p):
        z = self.Ztotal
        imports = self.extra.get('importsTotal')
        supply = self.extra.get('supplyTotal')
        supply_source = self.extra_sources.get('supplyTotal', '')
        if supply is None and imports is not None and self.x is not None:
            supply = self.x + imports
            supply_source = '총산출 + 연결한 수입계'
        final = self.extra.get('finalTotal')
        final_source = self.extra_sources.get('finalTotal', '')
        # Four explicitly linked domestic AND imported final-demand groups.
        keys = [prefix + k for prefix in ['fd_', 'fm_'] for k in ['consumption', 'investment', 'inventory', 'exports']]
        if final is None and all(k in self.extra for k in keys):
            final = sum(self.extra[k] for k in keys)
            final_source = '국산·수입 최종수요 4개 항목의 합'
        sx = scalar(self.x.sum()) if self.x is not None else None
        sv = scalar(self.va.sum()) if self.va is not None else None
        rows = []
        for j, m in enumerate(self.metrics):
            x = scalar(self.x[j]) if self.x is not None else None
            va = scalar(self.va[j]) if self.va is not None else None
            inter = scalar(z[j].sum()) if z is not None else None
            demand = scalar(supply[j]) if supply is not None else None
            f = scalar(final[j]) if final is not None else None
            rows.append(dict(code=m['code'], name=m['name'], output=x, valueAdded=va,
                             outputShare=share(x, sx), valueAddedShare=share(va, sv),
                             intermediateDemand=inter, finalDemand=f, totalDemand=demand,
                             intermediateDemandRate=share(inter, demand), finalDemandRate=share(f, demand),
                             balanceResidual=demand-inter-f if None not in [demand, inter, f] else None))
        return dict(rows=rows, outputTotal=sx, valueAddedTotal=sv,
                    sources=dict(supply=supply_source, final=final_source),
                    note='배분구조는 총거래 기준입니다. 총수요=총공급을 분모로 사용합니다. 최종수요를 잔액으로 추정하지 않습니다. 음수 재고·조정항목을 포함할 수 있습니다.')

    def learning(self, p):
        i = self.codes.index(p.get('supplier', self.codes[0]))
        j = self.codes.index(p.get('buyer', self.codes[0]))
        domestic = self.meta['modelBasis'] == 'domestic'
        z = self.Zd  # Model transaction matrix; total basis is explicitly labeled below.
        indexes = lambda k: list(range(max(0, min(k-1, self.n-3)), min(self.n, max(3, k+2))))
        ri, ci = indexes(i), indexes(j)
        tx = scalar(z[i, j]) if z is not None else None
        x = scalar(self.x[j]) if self.x is not None else None
        total_tx = scalar(self.Ztotal[i, j]) if self.Ztotal is not None else None
        imp_tx = scalar(self.Zm[i, j]) if self.Zm is not None else None
        input_total = scalar(self.Ztotal[:, j].sum()) if self.Ztotal is not None else None
        va = scalar(self.va[j]) if self.va is not None else None
        eco = self.economy({})['rows'][j]
        return dict(supplier=self.metrics[i], buyer=self.metrics[j], domestic=domestic,
                    rowCodes=[self.codes[k] for k in ri], rowNames=[self.names[k] for k in ri],
                    colCodes=[self.codes[k] for k in ci], colNames=[self.names[k] for k in ci],
                    grid=[[scalar(z[a,b]) if z is not None else None for b in ci] for a in ri],
                    transaction=tx, totalTransaction=total_tx, importTransaction=imp_tx,
                    output=x, intermediateInput=input_total, valueAdded=va,
                    inputResidual=x-input_total-va if None not in [x, input_total, va] else None,
                    allocation=eco, coefficient=float(self.A[i,j]), inverseCell=float(self.L[i,j]),
                    multiplier=float(self.L[:,j].sum()),
                    source=self.mapping.get('domesticSheet') or self.mapping['sheet'])
