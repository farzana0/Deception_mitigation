"""Residual-output steering with explicit absolute positions (batch size one)."""
import math
import torch


def position_bin(position):
    if position < 0:
        raise ValueError('Position must be nonnegative')
    return 0 if position == 0 else 1 if position <= 3 else 2 if position <= 11 else 3


def normalize_schedule(raw, residual_norms):
    """Each bin has sqrt(sum_l (||delta_l|| / typical_norm_l)^2) == 1."""
    relative = raw / residual_norms[:, None, None]
    denominator = relative.square().sum(dim=(0, 2)).sqrt()
    if (denominator < 1e-12).any():
        raise ValueError('Zero steering schedule')
    return raw / denominator[None, :, None]


class ResidualSteerer:
    def __init__(self, layers, fit, condition, layer=None, strength=0., c=0., audit=False):
        self.layers, self.fit, self.condition = layers, fit, condition
        self.layer, self.strength, self.c, self.audit = layer, strength, c, audit
        self.handles = []
        self.positions = None
        self.reset_stats()

    def reset_stats(self):
        self.eligible = self.steered = 0
        self.sum_sq = self.relative_sum_sq = 0.
        self.steps = 0
        self.trace = []

    def set_positions(self, absolute_positions, prompt_length):
        self.positions = absolute_positions - (prompt_length - 1)
        self.steps += int((self.positions >= 0).sum())

    def _hook(self, layer_id):
        i = self.fit['layers'].index(layer_id)
        def hook(module, args, out):
            h = out[0] if isinstance(out, tuple) else out
            if self.positions is None:
                raise RuntimeError('Decode positions must be set before forward')
            selected = (self.positions >= 0).nonzero(as_tuple=True)[0]
            if not len(selected):
                return out
            x = h[:, selected, :].float()
            pos = self.positions[selected]
            bins = torch.tensor([position_bin(int(v)) for v in pos], device=h.device)
            if self.audit:
                self.trace.append({'layer':layer_id,'positions':pos.tolist(),'bins':bins.tolist(),'sequence_length':h.shape[1]})
            if self.condition == 'sttp':
                stats = self.fit['sttp'][layer_id]
                u = stats['u'].to(h.device)
                p = x @ u
                gate = p < stats['t']
                delta = ((stats['mu_pos'] + self.c * stats['sd_pos'] - p) * gate).unsqueeze(-1) * u
            else:
                if self.strength == 0.:
                    self.eligible += x.shape[0]*x.shape[1]
                    return out  # Exact no-op, including BF16 rounding.
                name = 'joint' if self.condition == 'rank2' else 'pooled' if self.condition == 'pooled' else 'caa'
                if name == 'caa':
                    direction=self.fit['caa'][i].to(h.device)
                    direction=direction/direction.norm()*self.fit['residual_norms'][i].to(h.device)
                    delta=direction[None,None,:].expand_as(x)*self.strength
                else:
                    schedule=self.fit[name].to(h.device)
                    delta=schedule[i,bins,:][None,:,:].expand_as(x)*self.strength
            y=(x+delta).to(h.dtype)
            # Measure actual BF16 residual change, not only requested FP32 delta.
            actual=y.float()-x
            self.eligible += x.shape[0]*x.shape[1]
            self.steered += int((actual.norm(dim=-1)>0).sum())
            sq=actual.square().sum(dim=-1)
            self.sum_sq += float(sq.sum())
            self.relative_sum_sq += float((sq/(self.fit['residual_norms'][i].item()**2)).sum())
            result=h.clone();result[:,selected,:]=y
            return (result,*out[1:]) if isinstance(out,tuple) else result
        return hook

    def __enter__(self):
        if self.condition != 'baseline':
            ids=[self.layer] if self.condition in ('caa','sttp') else self.fit['layers']
            for layer in ids:
                self.handles.append(self.layers[layer].register_forward_hook(self._hook(layer)))
        return self

    def __exit__(self,*exc):
        for handle in self.handles: handle.remove()
        self.handles=[]

    def stats(self):
        return {'eligible_layer_tokens':self.eligible,'steered_layer_tokens':self.steered,
                'fraction_eligible_steered':self.steered/max(1,self.eligible),
                'realized_rms_l2_per_layer_token':math.sqrt(self.sum_sq/max(1,self.eligible)),
                'realized_relative_rms_total_per_step':math.sqrt(self.relative_sum_sq/max(1,self.steps)),
                'steps':self.steps}
