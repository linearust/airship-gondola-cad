# Selected Kailash gear evidence

The user supplied saved AliExpress product pages and the two retained 16T
images, then selected these exact options for CAD. These are seller statements
and nominal dimensions, not a received-part inspection. Project purchase keys
are internal identifiers, not supplier order codes.

| Item | 48T driver | 16T output |
| --- | --- | --- |
| Product | [Kailash HDAA-05 listing](https://www.aliexpress.com/item/1005011637445325.html) | [Kailash XC05-S1 listing](https://www.aliexpress.com/item/1005013121105173.html) |
| Selected option | 48 Teeth / 3 mm | 16 teeth / 3 mm; cart label `3mm3`, clarified by the dimension table |
| Module / pressure angle | 0.5 / 20° | 0.5 / 20° |
| Tooth type / process | External spur / hobbing, seller stated | External spur / hobbing, seller stated |
| Pitch / outside diameter | 24 / 25 mm | 8 / 9 mm |
| Face width / total length | 3 / 8 mm | 5 / 10 mm |
| Hub diameter / extension beyond teeth | 12 / 5 mm | 6.5 / 5 mm |
| Plain bore | Ø3 mm; H8 stated in description | Ø3 mm; tolerance unpublished; 3.17 and 4 mm are different options |
| Radial screw thread | M3 | M3 |
| Screw axis from hub end | Unpublished | 2.5 mm (7.5 mm from tooth-side end) |
| Material statement | Description: aluminium alloy; general attribute: alloy steel | Copper/copper alloy; exact alloy unspecified |
| Actual mass | Unmeasured | Unmeasured |

The 48T page's 38.7 g example belongs to **130T**, not 48T. The user explicitly
deferred material-conflict and weight resolution while authorizing the selected
geometry. Do not change the selection or substitute POM density because those
items are pending. Screw inclusion, length, point and tightening torque are not
established; M3 screw purchasing is deferred.

The 16T sectional drawing gives E=5, F=5, L=10 and J=2.5 mm. Its size table
identifies the 16T row C=8, D=9 and G=6.5 mm. Retained images:

- [Generic sectional dimensions](kailash_16t_dimensions.png)
- [Tooth-count dimension table](kailash_16t_table.png)

Calculated nominal mesh: centre distance 16 mm and output angle -3 times input
angle. A 3 mm driver tooth band centred within the 5 mm output band has 1 mm
axial allowance on each side before full face overlap is lost. This calculation
is not a backlash, tooth-profile, strength, manufacturing-tolerance or loaded
travel qualification. Check the complete CAD axial stack and received parts.
The 48T round bore does not mate directly with the X06 15T spline; the horn,
coupling and nominal-3mm input stub provide that connection.
