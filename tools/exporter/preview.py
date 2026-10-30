import numpy as np
from PIL import Image
Image.MAX_IMAGE_PIXELS=None

def sample(img, uv):
    H,W=img.shape[:2]
    x=np.clip((uv[:,0]*W).astype(int),0,W-1); y=np.clip(((1-uv[:,1])*H).astype(int),0,H-1)
    return img[y,x,:3].astype(np.float32)/255

def load_tex(base='tex/'):
    return dict(body=np.asarray(Image.open(base+'axolotl_body_basecolor.png')),
                gills=np.asarray(Image.open(base+'axolotl_gills_basecolor.png')),
                eyeL=np.asarray(Image.open(base+'axolotl_eye_L_basecolor.png')),
                eyeR=np.asarray(Image.open(base+'axolotl_eye_R_basecolor.png')))

def colors_for(meshname, uv, tex):
    if 'Body' in meshname: return sample(tex['body'],uv)
    if 'Gills' in meshname: return sample(tex['gills'],uv)
    if 'EyeL' in meshname: return sample(tex['eyeL'],uv)
    if 'EyeR' in meshname: return sample(tex['eyeR'],uv)
    return np.tile(np.array([.8,.9,1.],np.float32),(len(uv),1))

def raster(pos, tris, col, view, size=700, bg=(0.12,0.12,0.14), ext=None):
    """flat-shaded triangle raster, orthographic. view: 'side' (x=Z, y=Y), 'top' (x=X,y=-Z), 'front'(x=-X,y=Y)"""
    if view=='side': P=np.stack([pos[:,2],pos[:,1]],1); depth=pos[:,0]
    elif view=='top': P=np.stack([pos[:,0],-pos[:,2]],1); depth=-pos[:,1]
    else: P=np.stack([-pos[:,0],pos[:,1]],1); depth=-pos[:,2]
    if ext is None: ext=(P.min(0),P.max(0))
    lo,hi=ext; sc=(size-20)/max(hi-lo)
    S=(P-lo)*sc+10; S[:,1]=size-S[:,1]
    img=np.zeros((size,size,3),np.float32)+np.array(bg,np.float32); zb=np.full((size,size),-1e9,np.float32)
    # barycentric raster, vectorised per triangle batch
    a,b,c=tris[:,0],tris[:,1],tris[:,2]
    for t in range(len(tris)):
        ia,ib,ic=a[t],b[t],c[t]
        p0,p1,p2=S[ia],S[ib],S[ic]
        x0=int(max(min(p0[0],p1[0],p2[0]),0)); x1=int(min(max(p0[0],p1[0],p2[0])+1,size-1))
        y0=int(max(min(p0[1],p1[1],p2[1]),0)); y1=int(min(max(p0[1],p1[1],p2[1])+1,size-1))
        if x1<x0 or y1<y0: continue
        den=(p1[1]-p2[1])*(p0[0]-p2[0])+(p2[0]-p1[0])*(p0[1]-p2[1])
        if abs(den)<1e-9: continue
        xs,ys=np.meshgrid(np.arange(x0,x1+1)+.5,np.arange(y0,y1+1)+.5)
        l0=((p1[1]-p2[1])*(xs-p2[0])+(p2[0]-p1[0])*(ys-p2[1]))/den
        l1=((p2[1]-p0[1])*(xs-p2[0])+(p0[0]-p2[0])*(ys-p2[1]))/den
        l2=1-l0-l1
        m=(l0>=-1e-4)&(l1>=-1e-4)&(l2>=-1e-4)
        if not m.any(): continue
        z=l0*depth[ia]+l1*depth[ib]+l2*depth[ic]
        sub=zb[y0:y1+1,x0:x1+1]; upd=m&(z>sub)
        if not upd.any(): continue
        sub[upd]=z[upd]
        cc=(l0[...,None]*col[ia]+l1[...,None]*col[ib]+l2[...,None]*col[ic])
        img[y0:y1+1,x0:x1+1][upd]=cc[upd]
    return (np.clip(img,0,1)*255).astype(np.uint8)
