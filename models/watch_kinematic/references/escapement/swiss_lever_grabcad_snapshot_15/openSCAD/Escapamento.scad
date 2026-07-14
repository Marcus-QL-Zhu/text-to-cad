$fn=64; 
eps=0.1;
n=25;
// Escape Wheel
module corpo(){
    linear_extrude(height = 6)
    import(file = "\Escape_Wheel.DXF");

    cylinder(h = 15, r = 15, center = false);   
    translate([0, 0, 15])
    cylinder(h = 2, r = 20, center = false);}
    
 module cortes(){
     translate([0, 16, 6])
     cylinder(h = 20, r = 1, center = false);
     translate([0, 0, 5])
     cylinder(h = 20, r = 11, center = false);
     cylinder(h = 20, r = 6.5/2, center = false);}
     
module engrenagem(){
    difference(){
        corpo();
        cortes();}}
        
//Pallets
module pallets(){
    difference(){
    linear_extrude(height = 6)
    import(file = "\Pallets.DXF");}}
    
//Balance Wheel
module balanceWheel(){
    // Pin
    linear_extrude(height = 10)
    import(file = "\Balance_Wheel_Pin.DXF");
    // Flywheel
    translate([0, 0, 10])
    linear_extrude(height = 5)
    import(file = "\Balance_Wheel.DXF");
    
    // Shaft
    translate([0, 89.06, 0])
    difference(){
      cylinder(h = 15, r = 5, center = false);
      union() {
        cylinder(h = 31 , r = 6.5/2, center = true);
        translate([0, 4, 0])
        cube([4.5, 4, 8.5], center = true);
        }
    }}

//Spring
module spring(){
    r=5.5;
    thickness=1.2;
    loops=3.75;
    difference(){
        translate([0, 89.06, 0])
        rotate([0,0,90])
        linear_extrude(height=4 ) polygon(points= concat(
            [for(t = [90:360*loops]) 
                [(r-thickness+t/90)*sin(t),(r-thickness+t/90)*cos(t)]],
            [for(t = [360*loops:-1:90]) 
                [(r+t/90)*sin(t),(r+t/90)*cos(t)]]
                ));
        translate([0, 69.06, 0])
        cylinder(h = 10 , r = 3.2/2, center = true);}
        
    translate([0, 69.06, 0])
    difference(){
        cylinder(h = 4, r = 3, center = false);
        cylinder(h = 10 , r = 3.2/2, center = true);}
    
    translate([-2, 92.5, 0])
    cube([4, 3, 4], center = false);    
}


//Base
module base(){
  difference(){
    union(){
      hull(){
        translate([0, 0, -17.25])
        cylinder(h = 7.25, r = 7.5, center = false);
        translate([0, 89.62, -17.25])
        cylinder(h = 7.25, r = 7.5, center = false);
        translate([8.45, 70.93, -17.25])
        cylinder(h = 7.25, r = 10.25, center = false);
        translate([-8.45, 70.93, -17.25])
        cylinder(h = 7.25, r = 10.25, center = false);}
        
        // Curb Pin Holder 
        translate([-14.16, 50.79, -10-(-13.5/2)])
        rotate([0,0,18/2])
        cube([2.93, 8, 13.5], center = true);
        // Curb Pin Holder 
        translate([14.16, 50.79, -10-(-13.5/2)])
        rotate([0,0,-18/2])
        cube([2.93, 8, 13.5], center = true);
        
        // Suporte de Parede 
        difference(){
          translate([0, 89.62, -17.25])
          cylinder(h = 7.25, r = 20+3.2/2, center = false);
          translate([0, 89.62, -10-(7.25/2)])  
          cylinder(h = 10, r = 20-3.2/2, center = true);  
        }}
        
        
    union(){
      translate([0, 0, -17.25])
      cylinder(h = 15, r = 6.5/2, center = true);
      translate([0, 89.62, -17.25])
      cylinder(h = 15, r = 6.5/2, center = true);
      translate([14.16, 50.79, -10-(-13.5/2)])
      rotate([0,90,-18/2])
      cylinder(h = 15, r = 3.2/2, center = true);
      translate([-14.16, 50.79, -10-(-13.5/2)])
      rotate([0,90,18/2])
      cylinder(h = 15, r = 3.2/2, center = true);
      
      translate([0, 89.62, -20])
      rotate([0,0,180+25])
      
      for (i = [0:n]){
        echo(50*i/n, sin(50*i/n)*20, cos(50*i/n)*20);
        translate([sin(50*i/n)*20, cos(50*i/n)*20, 0 ])
        cylinder(h =20, r=3.2/2);
      }
    }       
}}


base();
spring();
balanceWheel();
engrenagem();
pallets();