package kr.ac.homeguard.photoviewer;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.RectF;
import android.view.MotionEvent;
import android.widget.ImageView;

/** Draws and edits a normalized rectangle in the displayed photo coordinates. */
public class ZoneImageView extends ImageView {
    final float[] zone = {0, 0, 1, 1};
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final RectF photoFrame = new RectF(), selectionFrame = new RectF();
    private float startX, startY;
    Runnable onZoneChanged;
    public ZoneImageView(Context context) { super(context); setScaleType(ScaleType.FIT_CENTER); setContentDescription("감시 영역 사진 · 드래그해서 영역 지정"); }
    private RectF photoRect() {
        if (getDrawable() == null) { photoFrame.setEmpty(); return photoFrame; }
        photoFrame.set(0, 0, getDrawable().getIntrinsicWidth(), getDrawable().getIntrinsicHeight());
        getImageMatrix().mapRect(photoFrame); photoFrame.offset(getPaddingLeft(), getPaddingTop()); return photoFrame;
    }
    @Override protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        RectF photo = photoRect(); if (photo.isEmpty()) return;
        RectF r = selectionFrame;
        r.set(photo.left + zone[0]*photo.width(), photo.top + zone[1]*photo.height(), photo.left + zone[2]*photo.width(), photo.top + zone[3]*photo.height());
        paint.setStyle(Paint.Style.FILL); paint.setColor(0x660E2033);
        canvas.drawRect(photo.left, photo.top, photo.right, r.top, paint);
        canvas.drawRect(photo.left, r.bottom, photo.right, photo.bottom, paint);
        canvas.drawRect(photo.left, r.top, r.left, r.bottom, paint);
        canvas.drawRect(r.right, r.top, photo.right, r.bottom, paint);
        paint.setColor(Color.rgb(35,220,155)); paint.setStyle(Paint.Style.STROKE); paint.setStrokeWidth(5);
        canvas.drawRect(r, paint);
    }
    private float clamp(float value) { return Math.max(0, Math.min(1, value)); }
    @Override public boolean onTouchEvent(MotionEvent event) {
        RectF photo = photoRect(); if (photo.isEmpty()) return false;
        float x = clamp((event.getX()-photo.left)/photo.width()), y = clamp((event.getY()-photo.top)/photo.height());
        if (event.getAction()==MotionEvent.ACTION_DOWN) { startX=x; startY=y; getParent().requestDisallowInterceptTouchEvent(true); return true; }
        if (event.getAction()==MotionEvent.ACTION_MOVE || event.getAction()==MotionEvent.ACTION_UP) {
            zone[0]=Math.min(startX,x); zone[1]=Math.min(startY,y); zone[2]=Math.max(startX,x); zone[3]=Math.max(startY,y);
            invalidate(); if(onZoneChanged!=null)onZoneChanged.run();
            if(event.getAction()==MotionEvent.ACTION_UP) { getParent().requestDisallowInterceptTouchEvent(false); performClick(); }
            return true;
        }
        if(event.getAction()==MotionEvent.ACTION_CANCEL)getParent().requestDisallowInterceptTouchEvent(false);
        return true;
    }
    @Override public boolean performClick() { super.performClick(); return true; }
}
