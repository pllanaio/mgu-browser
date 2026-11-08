/* Native X11 sibling-process prototype. No shell, file-transfer or clipboard API. */
#define _POSIX_C_SOURCE 200809L
#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <X11/keysym.h>
#include <X11/extensions/XShm.h>
#include <sys/ipc.h>
#include <sys/shm.h>
#include <poll.h>
#include <signal.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <time.h>
extern Bool XTestFakeKeyEvent(Display*,unsigned int,Bool,unsigned long);
extern Bool XTestFakeButtonEvent(Display*,unsigned int,Bool,unsigned long);
extern Bool XTestFakeMotionEvent(Display*,int,int,int,unsigned long);

#define MAX_COMMAND 128U
#define MAX_RGBA (4U*1024U*1024U-64U)
#define FRAME_HEADER 36U
#define RESPONSE_SIZE 24U
#define RESPONSE_COUNT 128U
enum { OP_EPOCH=1,OP_PING,OP_CAPTURE,OP_KEY,OP_POINTER,OP_WHEEL,OP_RELEASE,OP_STOP,OP_TEXT };
enum { OK=0,BAD_OPCODE,BAD_LENGTH,STALE,BUSY,UNSUPPORTED,INVALID,INTERNAL,SHUTTING_DOWN };
typedef struct {
 Display *display; Window root; int screen,xfd,width,height; unsigned int epoch;
 XImage *image; XShmSegmentInfo shm; int shm_attached; size_t shm_bytes;
 unsigned char *frame; size_t frame_length,frame_offset,frame_capacity; unsigned int frame_epoch;
 unsigned char responses[RESPONSE_COUNT][RESPONSE_SIZE]; unsigned int response_head,response_count,response_offset;
 unsigned char prefix[4],command[MAX_COMMAND]; unsigned int prefix_used,command_used,command_length;
 unsigned char held_keys[256],held_buttons[4]; unsigned int modifiers; KeyCode modifier_codes[4];
 int stopping,exit_code; double stop_deadline;
} Helper;
static volatile sig_atomic_t stop_signal;
static int signal_pipe[2]={-1,-1};
static int x_error;
static uint16_t u16(const unsigned char *p){return (uint16_t)p[0]|((uint16_t)p[1]<<8);}
static uint32_t u32(const unsigned char *p){return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);}
static int32_t i32(const unsigned char *p){return (int32_t)u32(p);}
static void put16(unsigned char *p,uint16_t x){p[0]=(unsigned char)x;p[1]=(unsigned char)(x>>8);}
static void put32(unsigned char *p,uint32_t x){p[0]=(unsigned char)x;p[1]=(unsigned char)(x>>8);p[2]=(unsigned char)(x>>16);p[3]=(unsigned char)(x>>24);}
static double monotonic(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec/1e9;}
static int nonblocking(int fd){int flags=fcntl(fd,F_GETFL);return flags<0?-1:fcntl(fd,F_SETFL,flags|O_NONBLOCK);}
static void interrupted(int sig){if(sig==SIGALRM)_exit(124);stop_signal=1;alarm(2);if(signal_pipe[1]>=0){unsigned char b=1;ssize_t ignored=write(signal_pipe[1],&b,1);(void)ignored;}}
static int on_x_error(Display*d,XErrorEvent*e){(void)d;(void)e;x_error=1;return 0;}
static int on_x_io_error(Display*d){(void)d;_exit(70);return 0;}
static void respond(Helper*h,unsigned int op,unsigned int status,unsigned int epoch,unsigned int id,unsigned int value){
 if(h->response_count==RESPONSE_COUNT){h->stopping=1;h->exit_code=71;h->stop_deadline=monotonic();return;}
 unsigned int slot=(h->response_head+h->response_count)%RESPONSE_COUNT;unsigned char *p=h->responses[slot];put32(p,20);p[4]=1;p[5]=(unsigned char)(op|128U);put16(p+6,(uint16_t)status);put32(p+8,epoch);put32(p+12,id);put32(p+16,h->epoch);put32(p+20,value);h->response_count++;
}
static void set_modifiers(Helper*h,unsigned int mods){
 for(int i=0;i<4;i++)if((h->modifiers&(1U<<i))&&!(mods&(1U<<i)))XTestFakeKeyEvent(h->display,h->modifier_codes[i],False,0);
 for(int i=0;i<4;i++)if(!(h->modifiers&(1U<<i))&&(mods&(1U<<i)))XTestFakeKeyEvent(h->display,h->modifier_codes[i],True,0);
 h->modifiers=mods;
}
static void release_input(Helper*h){
 if(!h->display)return;
 for(int i=1;i<=3;i++)if(h->held_buttons[i]){XTestFakeButtonEvent(h->display,(unsigned)i,False,0);h->held_buttons[i]=0;}
 for(int i=0;i<256;i++)if(h->held_keys[i]){XTestFakeKeyEvent(h->display,(unsigned)i,False,0);h->held_keys[i]=0;}
 set_modifiers(h,0);XFlush(h->display);
}
static void stop(Helper*h,int code){if(!h->stopping){h->stopping=1;h->exit_code=code;h->stop_deadline=monotonic()+.2;release_input(h);alarm(2);}}
static int geometry(Helper*h){
 Window root;int x,y;unsigned int w,height,border,depth;
 if(!XGetGeometry(h->display,h->root,&root,&x,&y,&w,&height,&border,&depth))return 0;
 if(!w||!height||w>1600||height>900||(uint64_t)w*height*4U>MAX_RGBA)return 0;
 h->width=(int)w;h->height=(int)height;return 1;
}
static int valid_modifiers(Helper*h,unsigned int mods){if(mods&~15U)return 0;for(int i=0;i<4;i++)if((mods&(1U<<i))&&!h->modifier_codes[i])return 0;return 1;}
static KeySym key_symbol(unsigned int id){
 static const KeySym keys[]={NoSymbol,XK_Tab,XK_Return,XK_Escape,XK_space,XK_BackSpace,XK_Delete,XK_Left,XK_Right,XK_Up,XK_Down,XK_Home,XK_End,XK_Page_Up,XK_Page_Down,XK_Insert};
 static const KeySym punctuation[]={XK_minus,XK_equal,XK_bracketleft,XK_bracketright,XK_backslash,XK_semicolon,XK_apostrophe,XK_grave,XK_comma,XK_period,XK_slash};
 if(id>0&&id<16)return keys[id];
 if(id>=16&&id<28)return XK_F1+id-16;
 if(id>=0x100&&id<0x11a)return XK_a+id-0x100;
 if(id>=0x130&&id<0x13a)return XK_0+id-0x130;
 if(id>=0x140&&id<0x14b)return punctuation[id-0x140];
 return NoSymbol;
}
static void drop_image(Helper*h){
 if(h->shm.shmid>=0)shmctl(h->shm.shmid,IPC_RMID,NULL);
 if(h->shm_attached){XShmDetach(h->display,&h->shm);h->shm_attached=0;}
 if(h->image){h->image->data=NULL;XDestroyImage(h->image);h->image=NULL;}
 if(h->shm.shmaddr&&h->shm.shmaddr!=(char*)-1){shmdt(h->shm.shmaddr);h->shm.shmaddr=NULL;}
 h->shm_bytes=0;h->shm.shmid=-1;
}
static int prepare_image(Helper*h){
 if(h->image&&h->image->width==h->width&&h->image->height==h->height)return 1;
 drop_image(h);memset(&h->shm,0,sizeof(h->shm));h->shm.shmid=-1;
 h->image=XShmCreateImage(h->display,DefaultVisual(h->display,h->screen),DefaultDepth(h->display,h->screen),ZPixmap,NULL,&h->shm,(unsigned)h->width,(unsigned)h->height);
 if(!h->image)return 0;
 if(h->image->bits_per_pixel!=32||h->image->byte_order!=LSBFirst||h->image->red_mask!=0xff0000||h->image->green_mask!=0xff00||h->image->blue_mask!=0xff){drop_image(h);return 0;}
 h->shm_bytes=(size_t)h->image->bytes_per_line*(size_t)h->height;if(h->shm_bytes>MAX_RGBA+3600U){drop_image(h);return 0;}
 h->shm.shmid=shmget(IPC_PRIVATE,h->shm_bytes,IPC_CREAT|0600);if(h->shm.shmid<0){drop_image(h);return 0;}
 h->shm.shmaddr=shmat(h->shm.shmid,NULL,0);if(h->shm.shmaddr==(char*)-1){shmctl(h->shm.shmid,IPC_RMID,NULL);drop_image(h);return 0;}
 /* Linux permits attaching an IPC_RMID segment while our own attachment lives.
    Mark before the synchronous X roundtrip so a stalled server cannot leak it. */
 if(shmctl(h->shm.shmid,IPC_RMID,NULL)){drop_image(h);return 0;}
 h->image->data=h->shm.shmaddr;h->shm.readOnly=False;x_error=0;
 if(!XShmAttach(h->display,&h->shm)){drop_image(h);return 0;}
 h->shm_attached=1;XSync(h->display,False);if(x_error){drop_image(h);return 0;}return 1;
}
static int capture(Helper*h,unsigned int id){
 if(!geometry(h)||!prepare_image(h))return UNSUPPORTED;
 size_t rgba=(size_t)h->width*(size_t)h->height*4U,total=FRAME_HEADER+rgba;
 if(h->frame_capacity<total){unsigned char *p=realloc(h->frame,total);if(!p)return INTERNAL;h->frame=p;h->frame_capacity=total;}
 x_error=0;if(!XShmGetImage(h->display,h->root,h->image,0,0,AllPlanes)||x_error)return INTERNAL;
 unsigned char *out=h->frame+FRAME_HEADER;for(int y=0;y<h->height;y++){const unsigned char *in=(unsigned char*)h->image->data+(size_t)y*h->image->bytes_per_line;for(int x=0;x<h->width;x++){*out++=in[2];*out++=in[1];*out++=in[0];*out++=255;in+=4;}}
 put32(h->frame,(uint32_t)(32U+rgba));put32(h->frame+4,0x4655474d);put16(h->frame+8,1);put16(h->frame+10,32);put32(h->frame+12,h->epoch);put32(h->frame+16,id);put32(h->frame+20,(unsigned)h->width);put32(h->frame+24,(unsigned)h->height);put32(h->frame+28,(unsigned)h->width*4U);put32(h->frame+32,1);h->frame_epoch=h->epoch;h->frame_offset=0;h->frame_length=total;return OK;
}
static int pointer(Helper*h,const unsigned char*p){
 unsigned int action=p[0],button=p[1],mods=u32(p+12);int32_t x=i32(p+4),y=i32(p+8);
 if(u16(p+2)||action>4||!valid_modifiers(h,mods)||!geometry(h)||x<0||y<0||x>=h->width||y>=h->height)return INVALID;
 if((action==0&&button)||(action!=0&&(button<1||button>3)))return INVALID;
 if((action==1&&h->held_buttons[button])||(action==2&&!h->held_buttons[button])||((action==3||action==4)&&h->held_buttons[button]))return INVALID;
 unsigned int old=h->modifiers;if(action<3)set_modifiers(h,action==2?old:mods);else set_modifiers(h,old|mods);
 XTestFakeMotionEvent(h->display,-1,x,y,0);
 if(action==1){XTestFakeButtonEvent(h->display,button,True,0);h->held_buttons[button]=1;}
 if(action==2){XTestFakeButtonEvent(h->display,button,False,0);h->held_buttons[button]=0;set_modifiers(h,mods);}
 if(action>=3){for(unsigned int i=0;i<(action==4?2U:1U);i++){XTestFakeButtonEvent(h->display,button,True,0);XTestFakeButtonEvent(h->display,button,False,0);}set_modifiers(h,old);}
 XFlush(h->display);return OK;
}
static int keyboard(Helper*h,const unsigned char*p){
 unsigned int id=u16(p),action=u16(p+2),mods=u32(p+4);KeySym sym=key_symbol(id);if(sym==NoSymbol||action>2||!valid_modifiers(h,mods))return INVALID;KeyCode code=XKeysymToKeycode(h->display,sym);if(!code)return UNSUPPORTED;
 if((action<2&&h->held_keys[code])||(action==2&&!h->held_keys[code]))return INVALID;
 unsigned int old=h->modifiers;
 if(action==0){set_modifiers(h,old|mods);XTestFakeKeyEvent(h->display,code,True,0);XTestFakeKeyEvent(h->display,code,False,0);set_modifiers(h,old);}
 else if(action==1){set_modifiers(h,mods);XTestFakeKeyEvent(h->display,code,True,0);h->held_keys[code]=1;}
 else{XTestFakeKeyEvent(h->display,code,False,0);h->held_keys[code]=0;set_modifiers(h,mods);}
 XFlush(h->display);return OK;
}
static int wheel(Helper*h,const unsigned char*p){
 int32_t x=i32(p),y=i32(p+4),dx=i32(p+8),dy=i32(p+12);unsigned int mods=u32(p+16);
 if(!valid_modifiers(h,mods)||dx< -8||dx>8||dy< -8||dy>8||!geometry(h)||x<0||y<0||x>=h->width||y>=h->height)return INVALID;
 unsigned int old=h->modifiers;set_modifiers(h,old|mods);XTestFakeMotionEvent(h->display,-1,x,y,0);
 for(int axis=0;axis<2;axis++){int32_t n=axis?dy:dx;unsigned int button=axis?(n<0?4U:5U):(n<0?6U:7U);if(n<0)n=-n;for(int32_t i=0;i<n;i++){XTestFakeButtonEvent(h->display,button,True,0);XTestFakeButtonEvent(h->display,button,False,0);}}
 set_modifiers(h,old);XFlush(h->display);return OK;
}
static void command(Helper*h){
 const unsigned char*p=h->command;unsigned int op=p[1],epoch=u32(p+4),id=u32(p+8),length=h->command_length-12U,status=OK,value=0;
 if(p[0]!=1||u16(p+2)){respond(h,op,INVALID,epoch,id,0);return;}
 if(op==OP_EPOCH){
  if(length)status=BAD_LENGTH;else if(!epoch||epoch<=h->epoch)status=STALE;else{release_input(h);h->epoch=epoch;if(h->frame_length&&h->frame_offset==0)h->frame_length=0;value=h->frame_length?h->frame_epoch:0;}
  respond(h,op,status,epoch,id,value);return;
 }
 if(epoch!=h->epoch||(!epoch&&op!=OP_STOP&&op!=OP_PING)){respond(h,op,STALE,epoch,id,0);return;}
 if(h->stopping){respond(h,op,SHUTTING_DOWN,epoch,id,0);return;}
 switch(op){
  case OP_PING:if(length)status=BAD_LENGTH;else value=(h->frame_length?1U:0U)|(h->modifiers?2U:0U);break;
  case OP_CAPTURE:if(length)status=BAD_LENGTH;else if(h->frame_length)status=BUSY;else{status=(unsigned)capture(h,id);if(status==OK)value=(unsigned)h->width*(unsigned)h->height*4U;}break;
  case OP_KEY:status=length==8?keyboard(h,p+12):BAD_LENGTH;break;
  case OP_POINTER:status=length==16?pointer(h,p+12):BAD_LENGTH;break;
  case OP_WHEEL:status=length==20?wheel(h,p+12):BAD_LENGTH;break;
  case OP_RELEASE:if(length)status=BAD_LENGTH;else release_input(h);break;
  case OP_STOP:if(length)status=BAD_LENGTH;else stop(h,0);break;
  case OP_TEXT:status=UNSUPPORTED;break;
  default:status=BAD_OPCODE;break;
 }
 respond(h,op,status,epoch,id,value);
}
static void read_commands(Helper*h){
 for(unsigned int count=0;count<32&&!h->stopping&&h->response_count<RESPONSE_COUNT;){
  unsigned char *target;size_t needed;
  if(h->prefix_used<4){target=h->prefix+h->prefix_used;needed=4U-h->prefix_used;}else{target=h->command+h->command_used;needed=h->command_length-h->command_used;}
  ssize_t n=read(0,target,needed);if(n<0){if(errno==EINTR)continue;if(errno==EAGAIN||errno==EWOULDBLOCK)return;stop(h,74);return;}
  if(n==0){if(h->prefix_used||h->command_used)respond(h,0,BAD_LENGTH,h->epoch,0,0);stop(h,0);return;}
  if(h->prefix_used<4){h->prefix_used+=(unsigned)n;if(h->prefix_used<4)continue;h->command_length=u32(h->prefix);if(h->command_length<12||h->command_length>MAX_COMMAND){respond(h,0,BAD_LENGTH,h->epoch,0,0);stop(h,65);return;}}
  else{h->command_used+=(unsigned)n;if(h->command_used==h->command_length){command(h);h->prefix_used=0;h->command_used=0;h->command_length=0;count++;}}
 }
}
static void write_responses(Helper*h){
 for(unsigned int n=0;n<32&&h->response_count;n++){
  unsigned char*p=h->responses[h->response_head];ssize_t w=write(1,p+h->response_offset,RESPONSE_SIZE-h->response_offset);
  if(w<0){if(errno==EINTR)continue;if(errno==EAGAIN||errno==EWOULDBLOCK)return;stop(h,74);h->response_count=0;return;}
  if(!w)return;
  h->response_offset+=(unsigned)w;if(h->response_offset==RESPONSE_SIZE){h->response_offset=0;h->response_head=(h->response_head+1)%RESPONSE_COUNT;h->response_count--;}
 }
}
static void write_frame(Helper*h){
 if(!h->frame_length||h->stopping)return;
 size_t bytes=h->frame_length-h->frame_offset;if(bytes>32768U)bytes=32768U;ssize_t n=write(3,h->frame+h->frame_offset,bytes);
 if(n<0){if(errno!=EAGAIN&&errno!=EWOULDBLOCK&&errno!=EINTR)stop(h,74);return;}h->frame_offset+=(size_t)n;if(h->frame_offset==h->frame_length){h->frame_offset=0;h->frame_length=0;}
}
int main(int argc,char**argv){
 (void)argv;if(argc!=1){fprintf(stderr,"No command-line operations are supported\n");return 64;}
 Helper h;memset(&h,0,sizeof(h));h.shm.shmid=-1;signal(SIGPIPE,SIG_IGN);signal(SIGTERM,interrupted);signal(SIGINT,interrupted);signal(SIGALRM,interrupted);
 if(pipe(signal_pipe)||nonblocking(signal_pipe[0])||nonblocking(signal_pipe[1])||nonblocking(0)||nonblocking(1)||nonblocking(3)){fprintf(stderr,"Separate stdin/stdout/frame fd3 pipes are required\n");return 64;}
 XSetErrorHandler(on_x_error);XSetIOErrorHandler(on_x_io_error);h.display=XOpenDisplay(NULL);if(!h.display){fprintf(stderr,"Private X display authentication failed\n");return 69;}h.screen=DefaultScreen(h.display);h.root=RootWindow(h.display,h.screen);h.xfd=ConnectionNumber(h.display);
 int op,event,error;if(!XShmQueryExtension(h.display)||!XQueryExtension(h.display,"XTEST",&op,&event,&error)||!geometry(&h)){fprintf(stderr,"Unsupported native display geometry or extensions\n");close(h.xfd);return 69;}
 KeySym mods[]={XK_Shift_L,XK_Control_L,XK_Alt_L,XK_Super_L};for(int i=0;i<4;i++)h.modifier_codes[i]=XKeysymToKeycode(h.display,mods[i]);
 for(;;){
  if(stop_signal)stop(&h,0);
  if(h.stopping&&(!h.response_count||monotonic()>=h.stop_deadline))break;
  struct pollfd p[4]={{0,(short)(!h.stopping&&h.response_count<RESPONSE_COUNT?POLLIN:0),0},{1,(short)(h.response_count?POLLOUT:0),0},{3,(short)(h.frame_length&&!h.stopping?POLLOUT:0),0},{signal_pipe[0],POLLIN,0}};
  int r=poll(p,4,h.stopping?20:1000);if(r<0){if(errno==EINTR)continue;stop(&h,74);continue;}
  if(p[3].revents&POLLIN){unsigned char buf[32];while(read(signal_pipe[0],buf,sizeof(buf))>0){}stop(&h,0);}
  if(p[0].revents&POLLIN)read_commands(&h);
  if(p[0].revents&(POLLHUP|POLLERR|POLLNVAL))stop(&h,0);
  if(p[1].revents&POLLOUT)write_responses(&h);
  if(p[1].revents&(POLLHUP|POLLERR|POLLNVAL)){h.response_count=0;stop(&h,74);}
  if(p[2].revents&POLLOUT)write_frame(&h);
  if(p[2].revents&(POLLHUP|POLLERR|POLLNVAL))stop(&h,74);
 }
 release_input(&h);XSync(h.display,False);drop_image(&h);XFlush(h.display);close(h.xfd);free(h.frame);close(signal_pipe[0]);close(signal_pipe[1]);alarm(0);return h.exit_code;
}
