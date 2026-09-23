import numpy as np, quilt as Q
cv, led, eng, w = Q.train(1, 0)
def g(block,k): return cv.read('AUDITOR',block,k)/Q.SCALE
seed='registrar/e1/xor/v1'; i=0
W=np.zeros((2,2)); Bs=[]
for j in Q.HID:
    for k in (0,1): W[k,j]=Q.krand(seed,i)/Q.SCALE; i+=1
    Bs.append(Q.krand(seed,i)/Q.SCALE); i+=2
V=np.array([Q.krand(seed,6+j)/Q.SCALE for j in Q.HID])
C=np.array([Q.krand(seed,8)/Q.SCALE])
Bv=np.array(Bs)
X=np.array([[0,0],[0,1],[1,0],[1,1]],float); T=np.array([0,1,1,0],float)
Zh=X@W+Bv; A=1/(1+np.exp(-Zh)); Zy=A@V+C; Y=1/(1+np.exp(-Zy))
dy=(Y-T)
gV=A.T@dy; gC=dy.sum()
da=dy[:,None]@V[None,:]; dh=da*A*(1-A)
gW=X.T@dh; gB=dh.sum(0)
print('canvas W0', [round(g('W',f'w0[{j}]'),5) for j in Q.HID])
print('ref   gW0', np.round(gW[0],5))
print('canvas W1', [round(g('W',f'w1[{j}]'),5) for j in Q.HID])
print('ref   gW1', np.round(gW[1],5))
print('canvas V ', [round(g('W2',f'v[{j}]'),5) for j in Q.HID])
print('ref   gV ', np.round(gV,5))
print('canvas Y ', [round(g('Y',f'y{c}'),5) for c in range(4)])
print('ref   Y  ', np.round(Y,5))
