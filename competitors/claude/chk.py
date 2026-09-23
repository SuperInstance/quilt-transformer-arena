"""Gradient cross-check v2: with lr = SCALE the canvas step is exactly -grad,
so reading (w_after - w_before) recovers the canvas gradient for comparison.
"""
import numpy as np, quilt as Q

SC = Q.SCALE

def snapshot(cv):
    return {b: {k: c.v for k, c in cs.items()} for b, cs in cv.blocks.items()}

cv, led, eng, w = Q.train(1, SC)          # lr = SCALE  ->  step == -grad
before = None
# re-run genesis on a fresh canvas to capture the pre-cycle params
cv0 = Q.Canvas(); Q.Engine(SC).genesis(cv0, 'registrar/e1/xor/v1')
before = {b: {k: c.v for k, c in cs.items()} for b, cs in cv0.blocks.items()}
after = {b: {k: c.v for k, c in cs.items()} for b, cs in cv.blocks.items()}

def f(b, k): return before[b][k] / SC
def grad(b, k): return (after[b][k] - before[b][k]) / SC

W = np.array([[f('W', f'w{k}[{j}]') for j in Q.HID] for k in (0, 1)])
B = np.array([f('B', f'b[{j}]') for j in Q.HID])
V = np.array([f('W2', f'v[{j}]') for j in Q.HID])
C = np.array([f('B2', 'c')])
X = np.array([[0., 0.], [0., 1.], [1., 0.], [1., 1.]])
T = np.array([0., 1., 1., 0.])

Zh = X @ W + B; A = 1 / (1 + np.exp(-Zh))
Zy = A @ V + C; Y = 1 / (1 + np.exp(-Zy))
print('hidden z  ref  ', np.round(Zh, 4).tolist())
print('hidden a  ref  ', np.round(A, 4).tolist())
print('hidden a canvas', [round(f('H', f'a{c}[{j}]'), 4) for c in range(4) for j in Q.HID])
print('out z     ref  ', np.round(Zy, 4).tolist())
print('out y     ref  ', np.round(Y, 5).tolist())
print('out y     canvas', [round(f('Y', f'y{c}'), 5) for c in range(4)])
print()
dy = Y - T
gV = A.T @ dy; gC = dy.sum()
da = dy[:, None] @ V[None, :]
dh = da * A * (1 - A)
gW = X.T @ dh; gB = dh.sum(0)
print('gW[0] canvas', [round(grad('W', f'w0[{j}]'), 6) for j in Q.HID])
print('gW[0] ref   ', np.round(gW[0], 6))
print('gW[1] canvas', [round(grad('W', f'w1[{j}]'), 6) for j in Q.HID])
print('gW[1] ref   ', np.round(gW[1], 6))
print('gV   canvas', [round(grad('W2', f'v[{j}]'), 6) for j in Q.HID])
print('gV   ref   ', np.round(gV, 6))
print('gB   canvas', [round(grad('B', f'b[{j}]'), 6) for j in Q.HID])
print('gB   ref   ', np.round(gB, 6))
print('gC   canvas', round(grad('B2', 'c'), 6), ' ref', round(float(gC), 6))
