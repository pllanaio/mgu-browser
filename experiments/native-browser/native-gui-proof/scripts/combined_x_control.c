#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <X11/extensions/XShm.h>
#include <sys/ipc.h>
#include <sys/shm.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
extern Bool XTestFakeKeyEvent(Display*,unsigned int,Bool,unsigned long);
extern Bool XTestFakeButtonEvent(Display*,unsigned int,Bool,unsigned long);
extern Bool XTestFakeMotionEvent(Display*,int,int,int,unsigned long);
static int errors;static int handler(Display*d,XErrorEvent*e){(void)d;(void)e;errors++;return 0;}
static double now(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec/1e9;}
static void pause_seconds(double n){if(n>0){struct timespec t={(time_t)n,(long)((n-(time_t)n)*1e9)};nanosleep(&t,NULL);}}
static void key(Display*d,const char*n,int down){KeySym sym=XStringToKeysym(n);if(sym==NoSymbol){fprintf(stderr,"Unknown native key\n");exit(2);}XTestFakeKeyEvent(d,XKeysymToKeycode(d,sym),down,0);}
static void press(Display*d,const char*n){key(d,n,1);key(d,n,0);}
static uint32_t crc(const unsigned char*p,size_t n){uint32_t h=2166136261U;for(size_t i=0;i<n;i++)h=(h^p[i])*16777619U;return h;}
static void ppm(XImage*im,const char*path){FILE*f=fopen(path,"wb");if(!f){perror("screenshot");exit(3);}fprintf(f,"P6\n%d %d\n255\n",im->width,im->height);unsigned char*row=malloc((size_t)im->width*3);for(int y=0;y<im->height;y++){for(int x=0;x<im->width;x++){unsigned long p=XGetPixel(im,x,y);row[3*x]=(p&im->red_mask)>>16;row[3*x+1]=(p&im->green_mask)>>8;row[3*x+2]=p&im->blue_mask;}fwrite(row,3,im->width,f);}free(row);fclose(f);}
int main(int argc,char**argv){if(argc<2)return 2;Display*d=XOpenDisplay(NULL);if(!d){fprintf(stderr,"Private native display authentication failed\n");return 1;}XSetErrorHandler(handler);int s=DefaultScreen(d);Window root=RootWindow(d,s);
 if(!strcmp(argv[1],"click")){if(argc<4)return 2;int b=argc>4?atoi(argv[4]):1;XTestFakeMotionEvent(d,-1,atoi(argv[2]),atoi(argv[3]),0);XTestFakeButtonEvent(d,b,True,0);XTestFakeButtonEvent(d,b,False,0);XSync(d,False);pause_seconds(.1);}
 else if(!strcmp(argv[1],"key")){if(argc<3)return 2;for(int i=3;i<argc;i++)key(d,argv[i],1);press(d,argv[2]);for(int i=argc-1;i>=3;i--)key(d,argv[i],0);XSync(d,False);pause_seconds(.08);}
 else if(!strcmp(argv[1],"text")){if(argc<3)return 2;const char*shifted="ABCDEFGHIJKLMNOPQRSTUVWXYZ~!@#$%^&*()_+{}|:\"<>?";for(const unsigned char*p=(unsigned char*)argv[2];*p;p++){if(*p<32||*p>126)return 2;int shift=strchr(shifted,*p)!=NULL;if(shift)key(d,"Shift_L",1);KeyCode c=XKeysymToKeycode(d,*p);XTestFakeKeyEvent(d,c,True,0);XTestFakeKeyEvent(d,c,False,0);if(shift)key(d,"Shift_L",0);}XSync(d,False);pause_seconds(.08);}
 else if(!strcmp(argv[1],"capture")||!strcmp(argv[1],"bench")){
  int w=DisplayWidth(d,s),h=DisplayHeight(d,s);XShmSegmentInfo info={0};XImage*im=XShmCreateImage(d,DefaultVisual(d,s),DefaultDepth(d,s),ZPixmap,NULL,&info,w,h);if(!im)return 4;size_t size=(size_t)im->bytes_per_line*h;info.shmid=shmget(IPC_PRIVATE,size,IPC_CREAT|0600);if(info.shmid<0)return 5;info.shmaddr=shmat(info.shmid,NULL,0);if(info.shmaddr==(char*)-1)return 6;info.readOnly=False;im->data=info.shmaddr;if(!XShmAttach(d,&info))return 7;XSync(d,False);shmctl(info.shmid,IPC_RMID,NULL);
  int frames=0,changed=0;uint32_t previous=0;double elapsed=0,mean=0,max=0;double seconds=!strcmp(argv[1],"bench")?atof(argv[2]):0;const char*path=!strcmp(argv[1],"bench")?argv[3]:argv[2];double start=now();clock_t cpu=clock();
  do{double t=now();if(!XShmGetImage(d,root,im,0,0,AllPlanes))return 8;uint32_t value=crc((unsigned char*)im->data,size);double ms=(now()-t)*1000;mean+=ms;if(ms>max)max=ms;changed+=frames==0||previous!=value;previous=value;frames++;if(seconds>0)pause_seconds(start+frames/30.0-now());}while(seconds>0&&now()-start<seconds);
  elapsed=now()-start;double cpu_seconds=(double)(clock()-cpu)/CLOCKS_PER_SEC;ppm(im,path);printf("{\"success\":%s,\"uid\":%d,\"width\":%d,\"height\":%d,\"seconds\":%.6f,\"fps\":%.3f,\"frames\":%d,\"changedFrames\":%d,\"captureCrcMeanMs\":%.3f,\"captureCrcMaxMs\":%.3f,\"captureCpuPercent\":%.3f,\"xErrors\":%d}\n",errors==0?"true":"false",getuid(),w,h,elapsed,frames/(elapsed?elapsed:1),frames,changed,mean/frames,max,100*cpu_seconds/(elapsed?elapsed:1),errors);
  XShmDetach(d,&info);XSync(d,False);im->data=NULL;XDestroyImage(im);shmdt(info.shmaddr);
 }else return 2;XCloseDisplay(d);return errors?1:0;}
